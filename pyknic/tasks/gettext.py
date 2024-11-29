# -*- coding: utf-8 -*-
# pyknic/tasks/gettext.py
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

import typing

from pyknic.lib.tasks.scheduler.chain_source import ChainedTask, __default_chained_tasks_registry__
from pyknic.lib.registry import register_api
from pyknic.lib.log import Logger
from pyknic.lib.gettext import GetTextWrapper
from pyknic.path import root_path


@register_api(__default_chained_tasks_registry__, ":gettext_task")
class GetTextInitTask(ChainedTask):
    """ This task creates a pre-defined localization object (GetTextWrapper)
    """

    __translations_loc__ = root_path / 'locales'  # where localization files are stored

    def start(self) -> None:
        """ The :meth:`.ChainedTask.start` method implementation
        """
        self.wait_for(':log_task')
        Logger.info('Setting up a localization structure')

        translations = GetTextWrapper(self.__translations_loc__.absolute())
        self.save_result(translations)

    def task_name(self) -> str:
        """ Return this task's name
        """
        return "gettext-init"

    @classmethod
    def dependencies(cls) -> typing.Optional[typing.Set[str]]:
        """ The :meth:`.ChainedTask.dependencies` method implementation
        """
        return {":log_task"}
