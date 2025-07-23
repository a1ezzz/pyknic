# -*- coding: utf-8 -*-

import asyncio
import io
import pytest
import threading
import typing

from pyknic.lib.tasks.aio_wrapper import AsyncWrapper

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
        def blocking_fn():
            nonlocal blocking_event, blocking_fn_result
            blocking_event.wait()
            return blocking_fn_result

        async def waiter_fn():
            nonlocal blocking_event
            await asyncio.sleep(0.5)
            blocking_event.set()

        caller = await AsyncWrapper.create(blocking_fn, thread_executor=executor)

        test_result, _ = await asyncio.gather(caller(), waiter_fn())
        assert(test_result is blocking_fn_result)

    @pyknic_async_test
    async def test_exception(self, module_event_loop: asyncio.AbstractEventLoop) -> None:

        def blocking_fn():
            raise ValueError('!')

        caller = await AsyncWrapper.create(blocking_fn)

        with pytest.raises(ValueError):
            await caller()
