
import argparse
import sys

import pyknic.tasks  # noqa: F401  # force tasks loading

from pyknic.lib.log import Logger
from pyknic.base_app import BaseApp
from pyknic.environment import PyknicLogLevel


class App(BaseApp):

    def start(self) -> None:
        print('Starting the App', file=sys.stderr)
        BaseApp.start(self)

        tasks_source = self.tasks_source()

        config_result = tasks_source.wait_for(tasks_source.datalog(), 'config_task')
        config = config_result.result  # type: ignore[union-attr]

        apps_enabled = [str(x) for x in config["pyknic"]["apps"]]
        apps_enabled.sort()

        for app_id in apps_enabled:
            Logger.info(f'Starting an app "{app_id}"')
            tasks_source.execute(app_id)

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
        args = App.parser().parse_args()

        log_level_int = args.verbose
        log_level_str = PyknicLogLevel.ERROR.value  # default value

        if log_level_int == 0:
            log_level_str = PyknicLogLevel.ERROR.value  # default value
        elif log_level_int == 1:
            log_level_str = PyknicLogLevel.WARNING.value  # default value
        elif log_level_int == 2:
            log_level_str = PyknicLogLevel.INFO.value  # default value
        elif log_level_int >= 3:
            log_level_str = PyknicLogLevel.DEBUG.value  # default value

        App.start_app(
            'pyknic:starter',
            log_level=PyknicLogLevel(log_level_str),
            config_file=args.config,
            config_dir=args.config_dir
        )


if __name__ == "__main__":
    App.main()
