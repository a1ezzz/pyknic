
import argparse
import os
import signal
import typing

from types import FrameType

import pyknic.tasks  # noqa: F401  # force tasks loading

from pyknic.tasks.log import LogTask
from pyknic.tasks.config import ConfigTask

from pyknic.lib.log import Logger
from pyknic.lib.verify import verify_value
from pyknic.lib.tasks.proto import TaskProto
from pyknic.lib.tasks.scheduler.scheduler import Scheduler
from pyknic.lib.tasks.scheduler.chain_source import ChainedTasksSource
from pyknic.lib.tasks.threaded_task import ThreadedTask


class App(TaskProto):

    __instance__ = None

    @verify_value(log_level=lambda x: x >= 0)
    def __init__(
        self,
        log_level: int = 0,
        config_file: typing.Optional[str] = None,
        config_dir: typing.Optional[str] = None
    ):
        TaskProto.__init__(self)
        self.__scheduler = Scheduler(task_timeout=60)
        self.__scheduler_thread = ThreadedTask(self.__scheduler, thread_name="pyknic:scheduler")

        self.__main_source = ChainedTasksSource()
        self.__main_source_thread = ThreadedTask(self.__main_source, thread_name="pyknic:chained_tasks_source")

        self.__log_level_int = log_level
        self.__config_file = config_file
        self.__config_dir = config_dir

    def __set_log_level(self) -> None:
        if self.__log_level_int == 0:
            os.environ[LogTask.__env_var_name__] = "ERROR"
        elif self.__log_level_int == 1:
            os.environ[LogTask.__env_var_name__] = "WARN"
        elif self.__log_level_int == 2:
            os.environ[LogTask.__env_var_name__] = "INFO"
        else:
            os.environ[LogTask.__env_var_name__] = "DEBUG"

    def __set_config_vars(self) -> None:
        if self.__config_file is not None:
            os.environ[ConfigTask.__app_file_config_envar__] = self.__config_file

        if self.__config_dir is not None:
            os.environ[ConfigTask.__app_dir_config_envar__] = self.__config_dir

    def start(self) -> None:
        print('Starting the App')

        self.__set_log_level()
        self.__set_config_vars()

        self.__scheduler_thread.start()
        self.__main_source_thread.start()

        self.__scheduler.subscribe(self.__main_source)
        self.__main_source.execute('log_task')
        self.__main_source.execute('config_task')

        config_result = self.__main_source.wait_for(
            self.__main_source.datalog(), 'config_task'
        )
        config = config_result.result  # type: ignore[union-attr]

        apps_enabled = [str(x) for x in config["pyknic"]["apps"]]
        apps_enabled.sort()

        for app_id in apps_enabled:
            Logger.info(f'Starting an app "{app_id}"')
            self.__main_source.execute(app_id)

    def stop(self) -> None:
        self.__main_source_thread.stop()
        self.__main_source_thread.wait()
        self.__main_source_thread.join()

        self.__scheduler_thread.stop()
        self.__scheduler_thread.wait()
        self.__scheduler_thread.join()

    @classmethod
    def terminate_app(cls, sig: int, frame: typing.Optional[FrameType]) -> None:
        print('Stop Request')
        if App.__instance__:
            App.__instance__.stop()
            App.__instance__ = None

    @classmethod
    def parser(cls) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(
            prog='pyknic',
            description='A fat program that do different magic'
        )
        parser.add_argument('-v', '--verbose', action='count', default=0, help='more flags more logs')
        parser.add_argument('-c', '--config', type=str, help='configuration file')
        parser.add_argument('-C', '--config-dir', type=str, help='configuration directory')

        return parser

    @classmethod
    def main(cls) -> None:
        args = cls.parser().parse_args()

        signal.signal(signal.SIGINT, cls.terminate_app)

        App.__instance__ = ThreadedTask(
            App(log_level=args.verbose, config_file=args.config, config_dir=args.config_dir),
            thread_name='pyknic:starter'
        )
        App.__instance__.start()
        App.__instance__.wait()


if __name__ == "__main__":
    App.main()
