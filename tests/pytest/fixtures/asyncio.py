# -*- coding: utf-8 -*-
# tests/pytest/asyncio_helpers.py
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

import asyncio
import pytest
import threading
import typing

from decorator import decorator
from watchfiles import awatch

from fixture_helpers import BaseFixture
from fixtures.event_loop import EventLoopDescriptor, EventLoop


class BaseAsyncFixture(BaseFixture):

    def __init__(self):
        BaseFixture.__init__(self)
        self.loop_descriptor = None
        self.__start_task = None
        self.stop_wrapper_obj = None

    async def start_async_service(self, loop_descriptor):
        pass

    async def wait_startup(self, loop_descriptor):
        pass

    async def flush_async(self, loop_descriptor):
        pass

    async def stop_async(self):
        pass

    async def start_async_wrapper(self, loop_descriptor):
        # note: may be called more than one time

        if self.loop_descriptor is None:
            self.loop_descriptor = loop_descriptor
        assert(self.loop_descriptor is loop_descriptor)

        if not self.__start_task:
            self.__start_task = asyncio.create_task(self.start_async_service(loop_descriptor))
            await self.wait_startup(loop_descriptor)

            self.stop_wrapper_obj = self.__stop_wrapper()
            self.loop_descriptor.add(self.stop_wrapper_obj)

    @classmethod
    def start(cls) -> typing.Any:
        return cls()

    async def __stop_wrapper(self):
        await self.stop_async()
        if self.__start_task is not None:
            await self.__start_task
            self.__start_task = None

    @classmethod
    def finalize(cls, start_result: typing.Any):
        # note: may be called more than one time
        if start_result.loop_descriptor:
            start_result.loop_descriptor.wait(start_result.stop_wrapper_obj)
            start_result.loop_descriptor = None


def pyknic_async_test(decorated_coroutine: typing.Callable[..., typing.Any]) -> typing.Callable[..., typing.Any]:

    def ordinary_fn(
        original_fn: typing.Callable[..., typing.Any], *args: typing.Any, **kwargs: typing.Any
    ) -> typing.Any:

        loop = EventLoop.loop()

        async def asynced_fn() -> typing.Any:
            for i in args:
                if isinstance(i, BaseAsyncFixture):
                    await i.start_async_wrapper(loop)

            await original_fn(*args, **kwargs)
            for i in args:
                if isinstance(i, BaseAsyncFixture):
                    await i.flush_async(loop)

        return loop.loop.run_until_complete(asynced_fn())

    return decorator(ordinary_fn)(decorated_coroutine)
