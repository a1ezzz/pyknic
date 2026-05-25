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

import signal
import typing

from types import FrameType

import pyknic.tasks  # noqa: F401  # force tasks loading

from pyknic.lib.tasks.proto import TaskProto
from pyknic.lib.tasks.scheduler.scheduler import Scheduler
from pyknic.lib.tasks.scheduler.chain_source import ChainedTasksSource
from pyknic.lib.tasks.threaded_task import ThreadedTask
from pyknic.environment import PyknicEnvVars, PyknicLogLevel


class BaseApp(TaskProto):

    __instance__: typing.Optional[ThreadedTask] = None

    def __init__(
        self,
        log_level: PyknicLogLevel = PyknicLogLevel.INFO,
        config_file: typing.Optional[str] = None,
        config_dir: typing.Optional[str] = None
    ):
        TaskProto.__init__(self)
        self.__scheduler = Scheduler(task_timeout=60)
        self.__scheduler_thread = ThreadedTask(self.__scheduler, thread_name="pyknic:scheduler")

        self.__main_source = ChainedTasksSource()
        self.__main_source_thread = ThreadedTask(self.__main_source, thread_name="pyknic:chained_tasks_source")

        self.__log_level = log_level
        self.__config_file = config_file
        self.__config_dir = config_dir

    def tasks_source(self) -> ChainedTasksSource:
        return self.__main_source

    def start(self) -> None:
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
        self.__main_source_thread.stop()
        self.__main_source_thread.wait()
        self.__main_source_thread.join()

        self.__scheduler_thread.stop()
        self.__scheduler_thread.wait()
        self.__scheduler_thread.join()

    @classmethod
    def terminate_app(cls, sig: int, frame: typing.Optional[FrameType]) -> None:
        if BaseApp.__instance__:
            BaseApp.__instance__.stop()
            BaseApp.__instance__ = None

    @classmethod
    def start_app(cls, thread_name: str, *args: typing.Any, **kwargs: typing.Any) -> None:
        signal.signal(signal.SIGINT, cls.terminate_app)

        BaseApp.__instance__ = ThreadedTask(cls(*args, **kwargs), thread_name=thread_name)
        BaseApp.__instance__.start()
        BaseApp.__instance__.wait()
