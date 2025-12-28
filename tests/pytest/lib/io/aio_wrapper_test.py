# -*- coding: utf-8 -*-

import asyncio
import inspect
import io
import time

import pytest
import threading
import typing

from pyknic.lib.io.aio_wrapper import AsyncWrapper, IOThrottler, cg, cag, as_ag, chain_sync_processor
from pyknic.lib.io.aio_wrapper import chain_async_processor

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

        assert(await cag(IOThrottler.async_copier(source_io, dest_io)) == 1024)
        assert(dest_io.getvalue() == b'!' * 1024)

    @pyknic_async_test
    async def test_async_copier_throttling(self, module_event_loop: asyncio.AbstractEventLoop) -> None:
        source_io = io.BytesIO(b'!' * 1000)
        dest_io = io.BytesIO()

        start_time = time.monotonic()
        await cag(IOThrottler.async_copier(source_io, dest_io, block_size=50, throttling=200))
        finish_time = time.monotonic()

        assert((finish_time - start_time) > 4)  # (1000 / 200) - 1 = 4

    def test_exceptions(self) -> None:
        th = IOThrottler(throttling=1000)
        with pytest.raises(RuntimeError):
            th.pause()

        th.start()
        with pytest.raises(RuntimeError):
            th.start()

    @pytest.mark.parametrize("reader_method", [IOThrottler().reader, IOThrottler.sync_reader])
    def test_reader(self, reader_method) -> None:
        bytes_io = io.BytesIO(b'!' * 1024)
        result = []

        for data in reader_method(bytes_io, block_size=500):
            result.append(data)

        assert(result == [b'!' * 500, b'!' * 500, b'!' * 24])

    @pytest.mark.parametrize("copier_method", [IOThrottler().copier, IOThrottler.sync_copier])
    def test_copier(self, copier_method) -> None:
        source_io = io.BytesIO(b'!' * 1024)
        dest_io = io.BytesIO()

        cg(copier_method(source_io, dest_io))
        assert(dest_io.getvalue() == b'!' * 1024)

    @pytest.mark.parametrize("writer_method", [IOThrottler().writer, IOThrottler.sync_writer])
    def test_writer(self, writer_method) -> None:

        def source() -> typing.Generator[bytes, None, None]:
            for _ in range(10):
                yield b'b' * 100

        bytes_io = io.BytesIO()
        assert(cg(writer_method(source(), bytes_io)) == 1000)
        assert(bytes_io.getvalue() == b'b' * 1000)

    @pyknic_async_test
    async def test_async_writer(self, module_event_loop: asyncio.AbstractEventLoop) -> None:

        def source() -> typing.Generator[bytes, None, None]:
            for _ in range(10):
                yield b'b' * 100

        bytes_io = io.BytesIO()
        await cag(IOThrottler.async_writer(source(), bytes_io))
        assert(bytes_io.getvalue() == b'b' * 1000)

    @pyknic_async_test
    async def test_async_writer_throttling(self, module_event_loop: asyncio.AbstractEventLoop) -> None:

        def source() -> typing.Generator[bytes, None, None]:
            for _ in range(10):
                yield b'b' * 100

        bytes_io = io.BytesIO()

        start_time = time.monotonic()
        await cag(IOThrottler.async_writer(source(), bytes_io, block_size=250, throttling=200))
        finish_time = time.monotonic()
        assert((finish_time - start_time) > 3)  # (1000 / 200) - 1 = 4, but! (1000 / 250) - 1 = 3!

    @pyknic_async_test
    async def test_async_reader_size_limit(
        self, module_event_loop: asyncio.AbstractEventLoop
    ) -> None:
        bytes_io = io.BytesIO(b'!' * 1024)
        result = []

        async for data in IOThrottler.async_reader(bytes_io, block_size=500, read_size=600):
            result.append(data)

        assert(result == [b'!' * 500, b'!' * 100])

    @pyknic_async_test
    async def test_async_reader_size_limit_exception(
        self, module_event_loop: asyncio.AbstractEventLoop
    ) -> None:
        bytes_io = io.BytesIO(b'!' * 100)

        with pytest.raises(ValueError):
            await cag(IOThrottler.async_reader(bytes_io, block_size=50, read_size=200))

    @pytest.mark.parametrize("copier_method", [IOThrottler().copier, IOThrottler.sync_copier])
    def test_copier_size_limit(self, copier_method) -> None:
        source_io = io.BytesIO(b'!' * 1024)
        dest_io = io.BytesIO()

        cg(copier_method(source_io, dest_io, copy_size=700))
        assert(dest_io.getvalue() == b'!' * 700)

    @pytest.mark.parametrize("copier_method", [IOThrottler().copier, IOThrottler.sync_copier])
    def test_copier_size_limit_exception(self, copier_method) -> None:
        source_io = io.BytesIO(b'!' * 100)
        dest_io = io.BytesIO()

        with pytest.raises(ValueError):
            cg(copier_method(source_io, dest_io, copy_size=700))

    @pytest.mark.parametrize("writer_method", [IOThrottler().writer, IOThrottler.sync_writer])
    def test_writer_size_limit(self, writer_method) -> None:

        def source() -> typing.Generator[bytes, None, None]:
            for _ in range(10):
                yield b'b' * 100

        bytes_io = io.BytesIO()
        cg(writer_method(source(), bytes_io, write_size=521))
        assert(bytes_io.getvalue() == b'b' * 521)

    @pytest.mark.parametrize("writer_method", [IOThrottler().writer, IOThrottler.sync_writer])
    def test_writer_size_limit_exception(self, writer_method) -> None:

        def source() -> typing.Generator[bytes, None, None]:
            for _ in range(10):
                yield b'b' * 100

        bytes_io = io.BytesIO()
        with pytest.raises(ValueError):
            cg(writer_method(source(), bytes_io, write_size=2000))

    def test_custom_throttling(self):
        throttling = IOThrottler(1)

        throttling.start()
        time.sleep(1)
        throttling += 10

        assert(7 < throttling.pause() < 10)  # there may be 9, but 7 is safe enough =)


def test_cp() -> None:
    data = (x for x in ((b'b' * 10, ) * 10))
    assert(cg(data) == 100)


@pytest.mark.parametrize(
    "gen_obj",
    [
        (x for x in ((b'b' * 10, ) * 10)),
        as_ag((x for x in ((b'b' * 10, ) * 10)))
    ]
)
@pyknic_async_test
async def test_cap(gen_obj) -> None:
    assert(await cag(gen_obj) == 100)


@pyknic_async_test
async def test_as_ap() -> None:
    gen_gen1 = (x for x in ((b'b' * 10,) * 10))
    gen_gen2 = (x for x in ((b'b' * 10,) * 10))

    async_gen = as_ag(gen_gen1)
    assert(inspect.isasyncgen(async_gen))

    result = []
    async for i in async_gen:
        result.append(i)

    assert(list(gen_gen2) == result)


def test_chain_sync_processor():

    input_data = [b'a'] * 10

    def processor1(s):
        for i in s:
            yield i + b'b'

    def processor2(s):
        for i in s:
            yield i + b'c'

    result = list(chain_sync_processor(input_data))
    assert(result == ([b'a'] * 10))

    result = list(chain_sync_processor(input_data, processor1))
    assert(result == ([b'ab'] * 10))

    result = list(chain_sync_processor(input_data, processor1, processor2))
    assert(result == ([b'abc'] * 10))


@pyknic_async_test
async def test_chain_async_processor(module_event_loop: asyncio.AbstractEventLoop):

    input_data = [b'a'] * 10

    async def processor1(s):
        async for i in s:
            yield i + b'b'

    async def processor2(s):
        async for i in s:
            yield i + b'c'

    result = []
    async for i in chain_async_processor(input_data):
        result.append(i)
    assert(result == ([b'a'] * 10))

    result = []
    async for i in chain_async_processor(input_data, processor1):
        result.append(i)
    assert(result == ([b'ab'] * 10))

    result = []
    async for i in chain_async_processor(input_data, processor1, processor2):
        result.append(i)
    assert(result == ([b'abc'] * 10))
