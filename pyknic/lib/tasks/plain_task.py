# -*- coding: utf-8 -*-
# pyknic/lib/tasks/plain_task.py
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

from pyknic.lib.tasks.proto import TaskProto, TaskResult


class PlainTask(TaskProto):
    """ This class may be treated as an adapter from any callable object to the `.TaskProto` class
    """

    def __init__(self, fn: typing.Callable[[], typing.Any]):
        """ Create a new task that executed the specified object

        :param fn: object to execute
        """
        TaskProto.__init__(self)
        self.__function = fn

    def start(self) -> None:
        """ The :meth:`.TaskProto.start` method implementation
        """
        self.emit(self.task_started)
        try:
            result = self.__function()
        except Exception as e:
            self.emit(self.task_completed, TaskResult(None, exception=e))
            return

        self.emit(self.task_completed, TaskResult(result))
