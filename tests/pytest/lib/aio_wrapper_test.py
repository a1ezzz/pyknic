# -*- coding: utf-8 -*-

import asyncio
import io
import time

import pytest
import threading
import typing

from pyknic.lib.aio_wrapper import AsyncWrapper, IOThrottler

from fixtures.asyncio import pyknic_async_test
from pyknic.lib.tasks.thread_executor import ThreadExecutor


class TestAsyncWrapper:

    @pytest.mark.parametrize("executor", (None, ThreadExecutor()))
    @pyknic_async_test
    async def test(
        self, module_event_loop: asyncio.AbstractEventLoop, executor: typing.Optional[ThreadExecutor]
    ) -> None:

        blocking_event = threading.Event()
        blocking_fn_result = object()

        def blocking_fn() -> object:
            nonlocal blocking_event, blocking_fn_result  # noqa: F824
            blocking_event.wait()
            return blocking_fn_result

        async def waiter_fn() -> None:
            nonlocal blocking_event  # noqa: F824
            await asyncio.sleep(0.5)
            blocking_event.set()

        caller = await AsyncWrapper.create(blocking_fn, thread_executor=executor)

        test_result, _ = await asyncio.gather(caller(), waiter_fn())
        assert(test_result is blocking_fn_result)

    @pyknic_async_test
    async def test_exception(self, module_event_loop: asyncio.AbstractEventLoop) -> None:

        def blocking_fn() -> None:
            raise ValueError('!')

        caller = await AsyncWrapper.create(blocking_fn)

        with pytest.raises(ValueError):
            await caller()


class TestIOThrottler:

    @pyknic_async_test
    async def test_async_reader(self, module_event_loop: asyncio.AbstractEventLoop) -> None:
        bytes_io = io.BytesIO(b'!' * 1024)
        result = []

        async for data in IOThrottler.async_reader(bytes_io, block_size=500):
            result.append(data)

        assert(result == [b'!' * 500, b'!' * 500, b'!' * 24])

    @pyknic_async_test
    async def test_async_reader_throttling(self, module_event_loop: asyncio.AbstractEventLoop) -> None:
        bytes_io = io.BytesIO(b'!' * 1000)
        result = []

        start_time = time.monotonic()
        async for data in IOThrottler.async_reader(bytes_io, block_size=100, throttling=200):
            result.append(data)
        finish_time = time.monotonic()

        assert((finish_time - start_time) > 4)  # (1000 / 200) - 1 = 4
        assert(result == ([b'!' * 100] * 10))

    @pyknic_async_test
    async def test_async_copier(self, module_event_loop: asyncio.AbstractEventLoop) -> None:
        source_io = io.BytesIO(b'!' * 1024)
        dest_io = io.BytesIO()

        await IOThrottler.async_copier(source_io, dest_io)
        assert(dest_io.getvalue() == b'!' * 1024)

    @pyknic_async_test
    async def test_async_copier_read_throttling(self, module_event_loop: asyncio.AbstractEventLoop) -> None:
        source_io = io.BytesIO(b'!' * 1000)
        dest_io = io.BytesIO()

        start_time = time.monotonic()
        await IOThrottler.async_copier(source_io, dest_io, block_size=250, read_throttling=200)
        finish_time = time.monotonic()

        assert((finish_time - start_time) > 3)  # (1000 / 200) - 1 = 4, but! (1000 / 250) - 1 = 3!

    @pyknic_async_test
    async def test_async_copier_write_throttling(self, module_event_loop: asyncio.AbstractEventLoop) -> None:
        source_io = io.BytesIO(b'!' * 1000)
        dest_io = io.BytesIO()

        start_time = time.monotonic()
        await IOThrottler.async_copier(source_io, dest_io, block_size=50, write_throttling=200)
        finish_time = time.monotonic()

        assert((finish_time - start_time) > 4)  # (1000 / 200) - 1 = 4

    @pyknic_async_test
    async def test_async_copier_read_write_throttling(self, module_event_loop: asyncio.AbstractEventLoop) -> None:
        source_io = io.BytesIO(b'!' * 1000)
        dest_io = io.BytesIO()

        start_time = time.monotonic()
        await IOThrottler.async_copier(source_io, dest_io, block_size=50, write_throttling=200, read_throttling=10000)
        finish_time = time.monotonic()

        assert((finish_time - start_time) > 4)  # (1000 / 200) - 1 = 4

    def test_exceptions(self) -> None:
        th = IOThrottler(throttling=1000)
        with pytest.raises(RuntimeError):
            th.pause()

        th.start()
        with pytest.raises(RuntimeError):
            th.start()

    def test_reader(self) -> None:
        bytes_io = io.BytesIO(b'!' * 1024)
        result = []

        for data in IOThrottler.reader(bytes_io, block_size=500):
            result.append(data)

        assert(result == [b'!' * 500, b'!' * 500, b'!' * 24])

    def test_copier(self) -> None:
        source_io = io.BytesIO(b'!' * 1024)
        dest_io = io.BytesIO()

        IOThrottler.copier(source_io, dest_io)
        assert(dest_io.getvalue() == b'!' * 1024)
