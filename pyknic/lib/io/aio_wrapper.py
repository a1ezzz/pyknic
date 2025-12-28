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
import functools
import inspect
import time
import typing

from pyknic.lib.tasks.proto import TaskProto
from pyknic.lib.tasks.plain_task import PlainTask
from pyknic.lib.tasks.thread_executor import ThreadExecutor
from pyknic.lib.tasks.threaded_task import ThreadedTask
from pyknic.lib.signals.extra import AsyncWatchDog
from pyknic.lib.verify import verify_value
from pyknic.lib.io import __default_block_size__, IOGenerator, IOAsyncGenerator, IOProcessor, IOAsyncProcessor


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

    @verify_value(read_size=lambda x: x is None or x > 0, block_size=lambda x: x is None or x > 0)
    @verify_value(throttling=lambda x: x is None or x > 0)
    def reader(
        self,
        io_obj: typing.IO[bytes],
        *,
        read_size: typing.Optional[int] = None,
        block_size: typing.Optional[int] = None
    ) -> IOGenerator:
        """A basic reader implementation that reads file-object in blocking mode, and yields chunks of data. A pause
        should be made after every chunk in order to respect throttling settings. The pause duration may be found
        with the :meth:`.IOThrottler.pause` method.

        :note: This or :meth:`.IOThrottler.writer`, :meth:`.IOThrottler.copier`, :meth:`.IOThrottler.start` methods
        may be called only once.

        :param io_obj: IO-object to read
        :param read_size: total number of bytes to read
        :param block_size: number of bytes to read on each blocking read request
        """

        if block_size is None:
            block_size = __default_block_size__

        if read_size is None:
            read_size = -1

        self.start()

        next_block = io_obj.read(block_size if read_size < 0 else min(block_size, read_size))

        while next_block and (not not read_size):
            block_len = len(next_block)
            self.__processed_bytes += block_len
            read_size -= block_len
            yield next_block

            next_block = io_obj.read(block_size if read_size < 0 else min(block_size, read_size))

        if read_size > 0:
            raise ValueError(f'Source object does not have enough data. "{read_size}" bytes are missing')

    @staticmethod
    def sync_reader(
        io_obj: typing.IO[bytes],
        *,
        read_size: typing.Optional[int] = None,
        block_size: typing.Optional[int] = None,
        throttling: typing.Optional[int] = None
    ) -> IOGenerator:
        """A blocking variant of :meth:`IOThrottler.reader` method. It sleeps in blocking mode in order to
        respect throttling settings. It is useful for running in a dedicated thread
        """

        throttler = IOThrottler(throttling)
        for block in throttler.reader(io_obj, read_size=read_size, block_size=block_size):
            yield block
            time.sleep(throttler.pause())

    @staticmethod
    async def async_reader(
        io_obj: typing.IO[bytes],
        *,
        read_size: typing.Optional[int] = None,
        block_size: typing.Optional[int] = None,
        throttling: typing.Optional[int] = None
    ) -> IOAsyncGenerator:
        """An asyncio variant of :meth:`IOThrottler.reader` method. It sleeps in asyncio mode in order to
        respect throttling settings.
        """

        throttler = IOThrottler(throttling)
        for block in throttler.reader(io_obj, read_size=read_size, block_size=block_size):
            yield block
            await asyncio.sleep(throttler.pause())

    def writer(
        self,
        source: typing.Generator[bytes, None, None],
        io_obj: typing.IO[bytes],
        *,
        write_size: typing.Optional[int] = None,
        block_size: typing.Optional[int] = None
    ) -> IOGenerator:
        """A basic writer implementation that writes file-object in blocking mode, and yields chunks of data that
        has been written. A pause should be made after every chunk in order to respect throttling settings.
        The pause duration may be found with the :meth:`.IOThrottler.pause` method.

        :note: This or :meth:`.IOThrottler.writer`, :meth:`.IOThrottler.copier`, :meth:`.IOThrottler.start` methods
        may be called only once.

        :param source: generator that yields data to write
        :param io_obj: IO-object to write to
        :param write_size: total number of bytes to write
        :param block_size: a maximum number of bytes to write on each blocking write request
        """

        def data_splitter(generated_data: bytes) -> IOGenerator:
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

        self.start()

        for data in source:
            for next_block in data_splitter(data):
                next_block_len = len(next_block)

                if 0 < write_size < next_block_len:
                    next_block = next_block[:write_size]
                    next_block_len = write_size

                io_obj.write(next_block)
                yield next_block

                self.__processed_bytes += next_block_len
                write_size -= next_block_len

            if not write_size:
                return

        if write_size > 0:
            raise ValueError(f'Source object does not have enough data. "{write_size}" bytes are missing')

    @staticmethod
    def sync_writer(
        source: typing.Generator[bytes, None, None],
        io_obj: typing.IO[bytes],
        *,
        write_size: typing.Optional[int] = None,
        block_size: typing.Optional[int] = None,
        throttling: typing.Optional[int] = None
    ) -> IOGenerator:
        """A blocking variant of :meth:`IOThrottler.writer` method. It sleeps in blocking mode in order to
        respect throttling settings. It is useful for running in a dedicated thread
        """

        throttler = IOThrottler(throttling)
        for written_chunk in throttler.writer(source, io_obj, write_size=write_size, block_size=block_size):
            yield written_chunk
            time.sleep(throttler.pause())

    @staticmethod
    async def async_writer(
        source: typing.Generator[bytes, None, None],
        io_obj: typing.IO[bytes],
        *,
        write_size: typing.Optional[int] = None,
        block_size: typing.Optional[int] = None,
        throttling: typing.Optional[int] = None
    ) -> IOAsyncGenerator:
        """An asyncio variant of :meth:`IOThrottler.__writer` method. It sleeps in asyncio mode in order to
        respect throttling settings
        """

        throttler = IOThrottler(throttling)
        for written_chunk in throttler.writer(source, io_obj, write_size=write_size, block_size=block_size):
            yield written_chunk
            await asyncio.sleep(throttler.pause())

    def copier(
        self,
        source_io_obj: typing.IO[bytes],
        destination_io_obj: typing.IO[bytes],
        *,
        copy_size: typing.Optional[int] = None,
        block_size: typing.Optional[int] = None
    ) -> IOGenerator:
        """A basic data copier implementation that copies data from one IO-object to other one. A pause should be made
        after every chunk in order to respect throttling settings. The pause duration may be found with
        the :meth:`.IOThrottler.pause` method. This method yields successfully copied chunks.

        :note: This or :meth:`.IOThrottler.writer`, :meth:`.IOThrottler.copier`, :meth:`.IOThrottler.start` methods
        may be called only once.

        :param source_io_obj: IO-object to read
        :param destination_io_obj: IO-object to write to
        :param copy_size: number of bytes to copy
        :param block_size: (optional) number of bytes to read/write on each blocking request
        """

        reader_throttler = IOThrottler()
        self.start()

        for block in reader_throttler.reader(source_io_obj, read_size=copy_size, block_size=block_size):
            destination_io_obj.write(block)
            self.__processed_bytes += len(block)

            yield block

    @staticmethod
    def sync_copier(
        source_io_obj: typing.IO[bytes],
        destination_io_obj: typing.IO[bytes],
        *,
        copy_size: typing.Optional[int] = None,
        block_size: typing.Optional[int] = None,
        throttling: typing.Optional[int] = None
    ) -> IOGenerator:
        """A blocking variant of :meth:`IOThrottler.copier` method. It sleeps in blocking mode in order to
        respect throttling settings. It is useful for running in a dedicated thread
        """

        throttler = IOThrottler(throttling)

        for block in throttler.copier(source_io_obj, destination_io_obj, copy_size=copy_size, block_size=block_size):
            yield block
            time.sleep(throttler.pause())

    @staticmethod
    async def async_copier(
        source_io_obj: typing.IO[bytes],
        destination_io_obj: typing.IO[bytes],
        *,
        copy_size: typing.Optional[int] = None,
        block_size: typing.Optional[int] = None,
        throttling: typing.Optional[int] = None
    ) -> IOAsyncGenerator:
        """An asyncio variant of :meth:`IOThrottler.copier` method. It sleeps in asyncio mode in order to
        respect throttling settings.
        """

        throttler = IOThrottler(throttling)

        for block in throttler.copier(source_io_obj, destination_io_obj, copy_size=copy_size, block_size=block_size):
            yield block
            await asyncio.sleep(throttler.pause())


def cg(source: IOGenerator) -> int:
    """Run over an IO generator and complete it.

    :param source: a generator that yields chunks of data.

    :returns: a total number of bytes
    """
    return sum((len(x) for x in source))


async def as_ag(source: IOGenerator) -> IOAsyncGenerator:
    """Convert general generator to an async one

    :param source: generator to convert
    """
    for i in source:
        yield i


async def cag(source: typing.Union[IOGenerator, IOAsyncGenerator]) -> int:
    """Run over an "IO processor" and complete it.

    :param source: "IO processor" that yields chunks of data.

    :returns: a total number of bytes
    """
    result = 0

    async for data in (source if inspect.isasyncgen(source) else as_ag(source)):
        result += len(data)
    return result


def chain_sync_processor(source: IOGenerator, *processors: IOProcessor) -> IOGenerator:
    """This function runs chunks from source (general generator) through the processors and yields result.

    :param source: ordinary generator that yields chunks of data to process.
    :param processors: processors to run
    """

    def dummy_processor(s: IOGenerator) -> IOGenerator:
        # this is just to make sure that there is one processor at least
        for i in s:
            yield i

    chain = functools.partial(dummy_processor, source)
    for processor in processors:
        chain = functools.partial(processor, chain())

    for chunk in chain():
        yield chunk


async def chain_async_processor(
    source: typing.Union[IOGenerator, IOAsyncGenerator], *processors: IOAsyncProcessor
) -> IOAsyncGenerator:
    """This function runs chunks from source (general generator or async generator) through the processors
    and yields result.

    :param source: generator (ordinary or async one) that yields chunks of data to process.
    :param processors: processors to run
    """

    async def dummy_processor(s: typing.Union[IOGenerator, IOAsyncGenerator]) -> IOAsyncGenerator:
        # this is just to make sure that there is one processor at least
        async for i in (s if inspect.isasyncgen(source) else as_ag(s)):
            yield i

    chain = functools.partial(dummy_processor, source)
    for processor in processors:
        chain = functools.partial(processor, chain())

    async for chunk in chain():
        yield chunk
