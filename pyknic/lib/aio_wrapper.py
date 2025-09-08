# -*- coding: utf-8 -*-
# pyknic/lib/aio_wrapper.py
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
import io
import time
import typing

from pyknic.lib.tasks.proto import TaskProto
from pyknic.lib.tasks.plain_task import PlainTask
from pyknic.lib.tasks.thread_executor import ThreadExecutor
from pyknic.lib.tasks.threaded_task import ThreadedTask
from pyknic.lib.signals.extra import AsyncWatchDog
from pyknic.lib.verify import verify_value


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

    async def __call__(self) -> typing.Any:
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


class IOThrottler:
    """ This class helps to pause for limiting IO requests
    """

    __default_block_size__ = 4096  # usual number of a block size in common FS

    @verify_value(throttling=lambda x: x is None or x > 0)
    def __init__(self, throttling: typing.Optional[typing.Union[int, float]] = None):
        """ Create a new throttler

        :param throttling: number of bytes per seconds this throttler should aim to
        """
        self.__throttling = throttling
        self.__start_point: typing.Optional[float] = None
        self.__processed_bytes = 0

    def start(self) -> None:
        """ Start timer for this throttler. May be started only once!
        """
        if self.__start_point is not None:
            raise RuntimeError('This throttler has already started.')

        if self.__throttling is not None:
            self.__start_point = time.monotonic()

        self.__processed_bytes = 0

    def __iadd__(self, other: int) -> "IOThrottler":
        """Increase number of already processed bytes

        :param other: number of bytes
        """
        self.__processed_bytes += other
        return self

    def pause(self) -> typing.Union[int, float]:
        """Return required pause this throttler needs
        """
        if self.__throttling is None:
            return 0

        if self.__start_point is None:
            raise RuntimeError('This throttler was not started.')

        elapsed = time.monotonic() - self.__start_point
        should_be = float(self.__processed_bytes) / self.__throttling
        return (should_be - elapsed) if should_be > elapsed else 0

    @staticmethod
    async def async_reader(
        io_obj: io.IOBase, *, block_size: typing.Optional[int] = None, throttling: typing.Optional[int] = None
    ) -> typing.AsyncGenerator[bytes, None]:
        """Read IO-object with throttling

        :param io_obj: IO-object to read
        :param block_size: number of bytes to read on each blocking read request
        :param throttling: number of bytes per seconds this reader should read at
        """

        if block_size is None:
            block_size = IOThrottler.__default_block_size__

        throttler = IOThrottler(throttling)
        throttler.start()

        next_block = io_obj.read(block_size)

        while next_block:
            throttler += len(next_block)
            yield next_block
            await asyncio.sleep(throttler.pause())
            next_block = io_obj.read(block_size)

    @staticmethod
    async def async_copier(
        source_io_obj: io.IOBase,
        destination_io_obj: io.IOBase,
        *,
        block_size: typing.Optional[int] = None,
        read_throttling: typing.Optional[int] = None,
        write_throttling: typing.Optional[int] = None
    ) -> None:
        """Copy data from one IO-object to other with throttling

        :param source_io_obj: IO-object to read
        :param destination_io_obj: IO-object to write to
        :param block_size: (optional) number of bytes to read/write on each blocking request
        :param read_throttling: (optional) number of bytes per seconds this reader should read at
        :param write_throttling: (optional) number of bytes per seconds this writer should write at
        """
        write_throttler = IOThrottler(write_throttling)
        write_throttler.start()

        async for data in IOThrottler.async_reader(source_io_obj, block_size=block_size, throttling=read_throttling):
            destination_io_obj.write(data)
            write_throttler += len(data)
            await asyncio.sleep(write_throttler.pause())
