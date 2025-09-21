# -*- coding: utf-8 -*-
# pyknic/lib/io/aio_wrapper.py
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
import time
import typing

from pyknic.lib.tasks.proto import TaskProto
from pyknic.lib.tasks.plain_task import PlainTask
from pyknic.lib.tasks.thread_executor import ThreadExecutor
from pyknic.lib.tasks.threaded_task import ThreadedTask
from pyknic.lib.signals.extra import AsyncWatchDog
from pyknic.lib.verify import verify_value
from pyknic.lib.io import __default_block_size__


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
    @verify_value(read_size=lambda x: x is None or x > 0, block_size=lambda x: x is None or x > 0)
    @verify_value(throttling=lambda x: x is None or x > 0)
    def __reader(
        io_obj: typing.IO[bytes],
        *,
        read_size: typing.Optional[int] = None,
        block_size: typing.Optional[int] = None,
        throttling: typing.Optional[int] = None
    ) -> typing.Generator[typing.Tuple[bytes, float], None, None]:
        """A basic reader implementation that reads file-object in blocking mode, and yields pauses (along with data)
        that should be made in order to respect throttling settings and to give away control so parallel code may run

        :param io_obj: IO-object to read
        :param read_size: total number of bytes to read
        :param block_size: number of bytes to read on each blocking read request
        :param throttling: number of bytes per seconds this reader should read at
        """

        if block_size is None:
            block_size = __default_block_size__

        if read_size is None:
            read_size = -1

        throttler = IOThrottler(throttling)
        throttler.start()

        next_block = io_obj.read(block_size if read_size < 0 else min(block_size, read_size))

        while next_block and (not not read_size):
            block_len = len(next_block)
            throttler += block_len
            read_size -= block_len
            yield next_block, throttler.pause()

            next_block = io_obj.read(block_size if read_size < 0 else min(block_size, read_size))

        if read_size > 0:
            raise ValueError(f'Source object does not have enough data. "{read_size}" bytes are missing')

    @staticmethod
    def reader(
        io_obj: typing.IO[bytes],
        *,
        read_size: typing.Optional[int] = None,
        block_size: typing.Optional[int] = None,
        throttling: typing.Optional[int] = None
    ) -> typing.Generator[bytes, None, None]:
        """A blocking variant of :meth:`IOThrottler.__reader` method. It sleeps in blocking mode in order to
        respect throttling settings. It is useful for running in a dedicated thread
        """

        for block, pause in IOThrottler.__reader(
            io_obj, read_size=read_size, block_size=block_size, throttling=throttling
        ):
            yield block
            time.sleep(pause)

    @staticmethod
    async def async_reader(
        io_obj: typing.IO[bytes],
        *,
        read_size: typing.Optional[int] = None,
        block_size: typing.Optional[int] = None,
        throttling: typing.Optional[int] = None
    ) -> typing.AsyncGenerator[bytes, None]:
        """An asyncio variant of :meth:`IOThrottler.__reader` method. It sleeps in asyncio mode in order to
        respect throttling settings.
        """

        for block, pause in IOThrottler.__reader(
            io_obj, read_size=read_size, block_size=block_size, throttling=throttling
        ):
            yield block
            await asyncio.sleep(pause)

    @staticmethod
    def __writer(
        source: typing.Generator[bytes, None, None],
        io_obj: typing.IO[bytes],
        *,
        write_size: typing.Optional[int] = None,
        block_size: typing.Optional[int] = None,
        throttling: typing.Optional[int] = None
    ) -> typing.Generator[typing.Tuple[int, float], None, None]:
        """A basic writer implementation that writes file-object in blocking mode, and yields pauses (along with data)
        that should be made in order to respect throttling settings and to give away control so parallel code may run

        :param source: generator that yields data to write
        :param io_obj: IO-object to write to
        :param write_size: total number of bytes to write
        :param block_size: a maximum number of bytes to write on each blocking write request
        :param throttling: number of bytes per seconds this writer should write at
        """

        def data_splitter(generated_data: bytes) -> typing.Generator[bytes, None, None]:
            nonlocal block_size

            if block_size is None:
                block_size = __default_block_size__

            start_pos = 0
            data_left = len(generated_data)
            while data_left > 0:
                yield generated_data[start_pos:(start_pos + block_size)]
                start_pos += block_size
                data_left -= block_size

        if write_size is None:
            write_size = -1

        throttler = IOThrottler(throttling)
        throttler.start()

        for data in source:
            for next_block in data_splitter(data):
                next_block_len = len(next_block)

                if 0 < write_size < next_block_len:
                    next_block = next_block[:write_size]
                    next_block_len = write_size

                io_obj.write(next_block)
                yield next_block_len, throttler.pause()

                throttler += next_block_len
                write_size -= next_block_len

            if not write_size:
                return

        if write_size > 0:
            raise ValueError(f'Source object does not have enough data. "{write_size}" bytes are missing')

    @staticmethod
    def writer(
        source: typing.Generator[bytes, None, None],
        io_obj: typing.IO[bytes],
        *,
        write_size: typing.Optional[int] = None,
        block_size: typing.Optional[int] = None,
        throttling: typing.Optional[int] = None
    ) -> int:
        """A blocking variant of :meth:`IOThrottler.__writer` method. It sleeps in blocking mode in order to
        respect throttling settings. It is useful for running in a dedicated thread

        :return: number of bytes that was written
        """

        write_counter = 0

        for write_increment, pause in IOThrottler.__writer(
            source,
            io_obj,
            write_size=write_size,
            block_size=block_size,
            throttling=throttling
        ):
            write_counter += write_increment
            time.sleep(pause)

        return write_counter

    @staticmethod
    async def async_writer(
        source: typing.Generator[bytes, None, None],
        io_obj: typing.IO[bytes],
        *,
        write_size: typing.Optional[int] = None,
        block_size: typing.Optional[int] = None,
        throttling: typing.Optional[int] = None
    ) -> int:
        """An asyncio variant of :meth:`IOThrottler.__writer` method. It sleeps in asyncio mode in order to
        respect throttling settings.

        :return: number of bytes that was written
        """

        write_counter = 0

        for write_increment, pause in IOThrottler.__writer(
            source,
            io_obj,
            write_size=write_size,
            block_size=block_size,
            throttling=throttling
        ):
            write_counter += write_increment
            await asyncio.sleep(pause)

        return write_counter

    @staticmethod
    def __copier(
        source_io_obj: typing.IO[bytes],
        destination_io_obj: typing.IO[bytes],
        *,
        copy_size: typing.Optional[int] = None,
        block_size: typing.Optional[int] = None,
        read_throttling: typing.Optional[int] = None,
        write_throttling: typing.Optional[int] = None
    ) -> typing.Generator[typing.Tuple[int, float], None, None]:
        """A basic data copier implementation that copies data from one IO-object to other one. It yields pauses that
        should be made in order to respect throttling settings and to give away control so parallel code may run

        :param source_io_obj: IO-object to read
        :param destination_io_obj: IO-object to write to
        :param copy_size: number of bytes to copy
        :param block_size: (optional) number of bytes to read/write on each blocking request
        :param read_throttling: (optional) number of bytes per seconds this reader should read at
        :param write_throttling: (optional) number of bytes per seconds this writer should write at
        """

        write_throttler = IOThrottler(write_throttling)
        write_throttler.start()

        for block, pause in IOThrottler.__reader(
            source_io_obj, read_size=copy_size, block_size=block_size, throttling=read_throttling
        ):
            yield 0, pause

            destination_io_obj.write(block)
            write_throttler += len(block)
            yield len(block), write_throttler.pause()

    @staticmethod
    def copier(
        source_io_obj: typing.IO[bytes],
        destination_io_obj: typing.IO[bytes],
        *,
        copy_size: typing.Optional[int] = None,
        block_size: typing.Optional[int] = None,
        read_throttling: typing.Optional[int] = None,
        write_throttling: typing.Optional[int] = None
    ) -> int:
        """A blocking variant of :meth:`IOThrottler.__copier` method. It sleeps in blocking mode in order to
        respect throttling settings. It is useful for running in a dedicated thread

        :return: number of bytes that was copied
        """

        copy_counter = 0
        for copy_increment, pause in IOThrottler.__copier(
            source_io_obj,
            destination_io_obj,
            copy_size=copy_size,
            block_size=block_size,
            read_throttling=read_throttling,
            write_throttling=write_throttling
        ):
            copy_counter += copy_increment
            time.sleep(pause)

        return copy_counter

    @staticmethod
    async def async_copier(
        source_io_obj: typing.IO[bytes],
        destination_io_obj: typing.IO[bytes],
        *,
        copy_size: typing.Optional[int] = None,
        block_size: typing.Optional[int] = None,
        read_throttling: typing.Optional[int] = None,
        write_throttling: typing.Optional[int] = None
    ) -> int:
        """An asyncio variant of :meth:`IOThrottler.__copier` method. It sleeps in asyncio mode in order to
        respect throttling settings.

        :return: number of bytes that was copied
        """

        copy_counter = 0

        for copy_increment, pause in IOThrottler.__copier(
            source_io_obj,
            destination_io_obj,
            copy_size=copy_size,
            block_size=block_size,
            read_throttling=read_throttling,
            write_throttling=write_throttling
        ):
            copy_counter += copy_increment
            await asyncio.sleep(pause)

        return copy_counter
