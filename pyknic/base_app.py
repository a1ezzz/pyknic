# -*- coding: utf-8 -*-
# pyknic/base_app.py
#
# Copyright (C) 2026 the pyknic authors and contributors
# <see AUTHORS file>
#
# This file is part of pyknic.
#
# pyknic is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# pyknic is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with pyknic.  If not, see <http://www.gnu.org/licenses/>.

# TODO: document the code
# TODO: write tests for the code

import os
import signal
import threading
import typing

from types import FrameType

try:
    import boto3  # noqa: F401 # read bellow

    # This early import (if any) fixes the following error:
    #
    #   File "/usr/lib/python3.13/threading.py", line 1506, in _register_atexit
    #     raise RuntimeError("can't register atexit after shutdown")
    # RuntimeError: can't register atexit after shutdown

except ImportError:
    pass

# TODO: import internal tasks the same way as it happens with external ones
import pyknic.tasks  # noqa: F401  # force tasks loading

from pyknic.lib.capability import iscapable
from pyknic.lib.log import Logger
from pyknic.lib.tasks.proto import TaskProto
from pyknic.lib.tasks.scheduler.scheduler import Scheduler
from pyknic.lib.tasks.scheduler.chain_source import ChainedTasksSource
from pyknic.lib.tasks.threaded_task import ThreadedTask
from pyknic.environment import PyknicEnvVars, PyknicLogLevel


class BaseApp(TaskProto):

    __stop_timeout__ = 5  # number of seconds to wait for a thread stopping

    def __init__(
        self,
        log_level: PyknicLogLevel = PyknicLogLevel.INFO,
        config_file: typing.Optional[str] = None,
        config_dir: typing.Optional[str] = None
    ):
        TaskProto.__init__(self)

        self.__instance_lock = threading.Lock()

        self.__scheduler = Scheduler(task_timeout=60)
        self.__scheduler_thread = ThreadedTask(self.__scheduler, thread_name="pyknic:scheduler")

        self.__main_source = ChainedTasksSource()
        self.__main_source_thread = ThreadedTask(self.__main_source, thread_name="pyknic:chained_tasks_source")

        self.__log_level = log_level
        self.__config_file = config_file
        self.__config_dir = config_dir

    def instance_lock(self) -> threading.Lock:
        return self.__instance_lock

    def tasks_source(self) -> ChainedTasksSource:
        return self.__main_source

    def start(self) -> None:

        with self.instance_lock():
            PyknicEnvVars.export_settings(
                log_level=self.__log_level.value,
                dir_config=(self.__config_dir if self.__config_dir else ''),
                file_config=(self.__config_file if self.__config_file else '')
            )

            self.__scheduler_thread.start()
            self.__scheduler_thread.wait_initialization(60)
            self.__main_source_thread.start()
            self.__main_source_thread.wait_initialization(60)

            self.__scheduler.subscribe(self.__main_source)
            self.__main_source.execute('log_task')
            self.__main_source.execute('config_task')

    def stop(self) -> None:
        if not self.__main_source_thread.join():
            self.__main_source_thread.stop()
            self.__main_source_thread.wait(timeout=self.__stop_timeout__)
            self.__main_source_thread.join()

        if not self.__scheduler_thread.join():
            self.__scheduler_thread.stop()
            self.__scheduler_thread.wait(timeout=self.__stop_timeout__)
            self.__scheduler_thread.join()

    def setup_singals_handler(self) -> None:

        def terminate_app_handler(sig: int, frame: typing.Optional[FrameType]) -> None:

            with self.instance_lock():

                if iscapable(self, TaskProto.terminate):
                    self.terminate()
                else:
                    self.stop()

                running_threads = threading.enumerate()
                if len(running_threads) > 1:
                    Logger.critical(
                        f'Unable to stop an app because there are multiple running threads ({running_threads})! '
                        'We will terminate this app the hard way'
                    )
                    os.kill(0, signal.SIGKILL)

        signal.signal(signal.SIGINT, terminate_app_handler)
        signal.signal(signal.SIGTERM, terminate_app_handler)
