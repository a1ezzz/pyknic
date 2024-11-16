# -*- coding: utf-8 -*-
# pyknic/tasks/log.py
#
# Copyright (C) 2024 the pyknic authors and contributors
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

import logging
import os
import uuid

from pyknic.lib.datalog.proto import DatalogProto
from pyknic.lib.tasks.scheduler.chain_source import ChainedTaskProto, __default_chained_tasks_registry__
from pyknic.lib.tasks.scheduler.chain_source import DependenciesDescription
from pyknic.lib.registry import register_api
from pyknic.lib.log import Logger


@register_api(__default_chained_tasks_registry__, ":log_task")
class LogTask(ChainedTaskProto):
    """ This task sets up the project's logger
    """

    __env_var_name__ = "PYKNIC_LOG_LEVEL"  # defines an environment variable for log level

    def start(self) -> None:
        """ Tweak the logger
        """
        if LogTask.__env_var_name__ not in os.environ:
            raise ValueError(f'The "{LogTask.__env_var_name__}" variable was not set')

        log_level_str = os.environ[LogTask.__env_var_name__]
        if log_level_str not in ('ERROR', 'WARN', 'INFO', 'DEBUG'):
            raise ValueError(f'Unknown value of "{LogTask.__env_var_name__}" -- {log_level_str}')

        formatter = logging.Formatter(
            '[%(name)s] [%(threadName)s] [%(levelname)s] [%(asctime)s] %(message)s',
            '%Y-%m-%d %H:%M:%S'
        )

        handler = logging.StreamHandler()
        handler.setFormatter(formatter)

        log_level = getattr(logging, log_level_str)
        Logger.addHandler(handler)
        Logger.setLevel(log_level)

        Logger.info('Logger was set up')

    def task_name(self) -> str:
        """ Return this task's name
        """
        return "logger-setter"

    @classmethod
    def dependencies(cls) -> DependenciesDescription:
        """ Return "dependencies"
        """
        return DependenciesDescription()

    @classmethod
    def create(cls, datalog: DatalogProto, uid: uuid.UUID) -> 'ChainedTaskProto':
        """ Create a task
        """
        return cls()
