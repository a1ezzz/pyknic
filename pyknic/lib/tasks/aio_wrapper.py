# -*- coding: utf-8 -*-
# pyknic/lib/tasks/aio_wrapper.py
#
# Copyright (C) 2025 the pyknic authors and contributors
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
import typing

from pyknic.lib.tasks.proto import TaskProto
from pyknic.lib.tasks.plain_task import PlainTask
from pyknic.lib.tasks.thread_executor import ThreadExecutor
from pyknic.lib.tasks.threaded_task import ThreadedTask
from pyknic.lib.signals.extra import AsyncWatchDog


class AsyncWrapper:
    """This class wraps thread-running and async awaiting routine into a "single" call."""

    # TODO: make it to work with TaskProto.stop and TaskProto.terminate

    def __init__(
        self,
        task: TaskProto,
        loop: asyncio.AbstractEventLoop,
        thread_executor: typing.Optional[ThreadExecutor] = None
    ) -> None:
        """Create a new wrapper

        :param task: the task to start
        :param loop: loop inside which call will be made
        :param thread_executor: thread executor to execute a task with (if None then a new
        thread will be created)
        """
        self.__task = task
        self.__watchdog = AsyncWatchDog(loop, self.__task, TaskProto.task_completed)
        self.__executor = thread_executor

    async def __call__(self):
        """Execute a task in asynchronous way."""

        if self.__executor is not None:
            task_executor = self.__executor.start_async(self.__task)
        else:
            threaded_task = ThreadedTask(self.__task)
            task_executor = threaded_task.start_async()

        watchdog_future = await self.__watchdog.watchdog_future()
        await asyncio.gather(task_executor, watchdog_future)
        watchdog_result = watchdog_future.result()

        if watchdog_result.value.exception:
            raise watchdog_result.value.exception

        return watchdog_result.value.result

    @classmethod
    async def create(
        cls,
        fn: typing.Callable[[], typing.Any],
        loop: typing.Optional[asyncio.AbstractEventLoop] = None,
        thread_executor: typing.Optional[ThreadExecutor] = None
    ) -> "AsyncWrapper":
        """Create a new wrapper

        :param fn: the function to start (to wrap)
        :param loop: same as loop in the `.meth:AsyncWrapper.__init__` method
        :param thread_executor: same as thread_executor in the `.meth:AsyncWrapper.__init__` method
        """

        return cls(PlainTask(fn), loop if loop else asyncio.get_event_loop(), thread_executor)
