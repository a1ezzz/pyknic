# -*- coding: utf-8 -*-
# pyknic/lib/tasks/threaded_task.py
#
# Copyright (C) 2016-2024 the pyknic authors and contributors
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

import threading
import typing

from pyknic.lib.capability import iscapable
from pyknic.lib.tasks.proto import TaskProto, TaskResult, TaskStartError
from pyknic.lib.tasks.plain_task import PlainTask
from pyknic.lib.thread import CriticalResource


class ThreadedTask(TaskProto, CriticalResource):
    """ This class helps to run a task in a separate thread
    """

    def __init__(self, task: TaskProto, cr_timeout: typing.Union[int, float, None] = None):
        """ Create a task that will start a thread

        :param task: a task to run in a thread
        :param cr_timeout: timeout for exclusive access to methods (same as timeout
        in the :meth:`.CriticalResource.__init__` method)
        """
        TaskProto.__init__(self)
        CriticalResource.__init__(self, cr_timeout)
        self.__task = task
        self.__thread = None

        if iscapable(self.__task, TaskProto.stop):
            self.append_capability(TaskProto.stop, self.__stop)

        if iscapable(self.__task, TaskProto.terminate):
            self.append_capability(TaskProto.terminate, self.__terminate)

    @CriticalResource.critical_section
    def start(self) -> None:
        """ The :meth:`.TaskProto.start` method implementation
        """
        if self.__thread is not None:
            raise TaskStartError('A task is started already')

        self.__thread = threading.Thread(target=self.__threaded_function)
        self.__thread.start()

    def __threaded_function(self) -> None:
        """ Function that will be executed by a thread
        """
        self.emit(self.task_started)
        try:
            self.__task.start()  # result is always None
        except Exception as e:
            self.emit(self.task_completed, TaskResult(exception=e))
            return

        self.emit(self.task_completed, TaskResult())

    @CriticalResource.critical_section
    def __stop(self) -> None:
        """ The :meth:`.TaskProto.stop` method implementation. Will be used if an original task has a stop capability
        """
        self.__task.stop()

    @CriticalResource.critical_section
    def __terminate(self) -> None:
        """ The :meth:`.TaskProto.terminate` method implementation. Will be used if an original task has a termination
        capability
        """
        self.__task.terminate()

    @CriticalResource.critical_section
    def join(self) -> bool:
        """ Join started thread. Every thread must be joined at least once

        :return: True if thread was joined, False otherwise
        """
        is_alive = False
        if self.__thread:
            self.__thread.join(0)
            is_alive = self.__thread.is_alive()
            if not is_alive:
                self.__thread = None
        return not is_alive

    @staticmethod
    def plain_task(
        fn: typing.Callable[[], typing.Any], cr_timeout: typing.Union[int, float, None] = None
    ) -> 'ThreadedTask':
        """ Return ThreadedTask that is based by the simple callable
        """
        return ThreadedTask(PlainTask(fn), cr_timeout)

    def __del__(self) -> None:
        """ Finalize this object and check that thread was joined
        """
        # TODO: create a test for this (straightforward implementation didn't work)
        if self.__thread:
            raise RuntimeError("A thread wasn't awaited")
