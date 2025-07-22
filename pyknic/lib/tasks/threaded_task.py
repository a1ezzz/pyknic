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

import asyncio
import threading
import traceback
import typing

from pyknic.lib.log import Logger
from pyknic.lib.capability import iscapable
from pyknic.lib.signals.extra import AsyncWatchDog
from pyknic.lib.signals.proto import Signal
from pyknic.lib.tasks.proto import TaskProto, TaskResult, TaskStartError
from pyknic.lib.tasks.plain_task import PlainTask
from pyknic.lib.thread import CriticalResource


class ThreadedTask(TaskProto, CriticalResource):
    """ This class helps to run a task in a separate thread
    """

    thread_ready = Signal(TaskProto)  # signal is emitted when a thread is ready to join
    thread_joined = Signal(TaskProto)  # signal is emitted when a thread joined

    def __init__(
        self,
        task: TaskProto,
        cr_timeout: typing.Union[int, float, None] = None,
        thread_name: typing.Optional[str] = None
    ):
        """ Create a task that will start a thread

        :param task: a task to run in a thread
        :param cr_timeout: timeout for exclusive access to methods (same as timeout
        in the :meth:`.CriticalResource.__init__` method)
        :param thread_name: name of a thread to create
        """
        TaskProto.__init__(self)
        CriticalResource.__init__(self, cr_timeout)
        self.__task = task
        self.__thread = None
        self.__thread_name = thread_name

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

        self.__thread = threading.Thread(target=self.__threaded_function, name=self.__thread_name)
        self.__thread.start()

    def __threaded_function(self) -> None:
        """ Function that will be executed by a thread
        """
        self.emit(self.task_started)
        try:
            self.__task.start()  # result is always None
        except Exception as e:
            Logger.error(f'The "{self.__task_id()}" task failed with an error: {e}\n{traceback.format_exc()}')
            self.emit(self.thread_ready, self.__task)
            self.emit(self.task_completed, TaskResult(exception=e))
            return

        self.emit(self.thread_ready, self.__task)
        self.emit(self.task_completed, TaskResult())

    def __task_id(self) -> str:
        """ Return id of a task that is executed
        """
        return self.__task.task_name() if self.__task.task_name() else str(self.__task)  # type: ignore[return-value]

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
        if self.__thread is not None:
            self.__thread.join(0)
            is_alive = self.__thread.is_alive()
            if not is_alive:
                self.__thread = None
                self.emit(ThreadedTask.thread_joined, self.__task)
        return not is_alive

    def wait(self, timeout: typing.Union[int, float, None] = None) -> None:
        """ Do not call a threaded task to stop, but wait till it stops

        :param timeout: a timeout with which this method should be called. If value is None then this function
        will wait forever, if value is negative or zero, then this function will poll current state,
        otherwise -- number of seconds to wait for

        :note: Use this method without timeout as a last resort only. Since it blocks other methods of this class
        """
        with self.critical_context():

            if self.__thread is not None:
                if timeout is None:
                    self.__thread.join()
                else:
                    self.__thread.join(timeout=timeout)

        self.join()

    async def async_wait(self, timeout: typing.Union[int, float, None] = None) -> None:
        """Wait for the thread to finish in asyncio-way

        :param timeout: a timeout with which this method should be called. If value is None then this function
        will wait forever, if value is negative or zero, then this function will poll current state,
        otherwise -- number of seconds to wait for
        """

        with self.critical_context():
            if self.__thread is None:
                return

            watchdog = AsyncWatchDog(asyncio.get_event_loop(), self, ThreadedTask.thread_ready)

        watchdog_future = await watchdog.wait(timeout=timeout)
        if watchdog_future.done():
            self.wait()  # force thread to join since callback may be received earlier

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
        # TODO: create a test for this (straightforward test implementation didn't work)
        if self.__thread:
            raise RuntimeError(f"A thread wasn't awaited (the task -- {self.__task_id()})")
