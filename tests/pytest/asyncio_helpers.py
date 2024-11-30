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

# TODO: document the code

import asyncio
import pytest
import typing

from decorator import decorator


class BaseAsyncFixture:

    def __init__(self) -> None:
        self.loop: asyncio.AbstractEventLoop | None = None
        self.__task: typing.Awaitable[typing.Any] | None = None

    async def _init_fixture(self) -> None:
        pass

    async def __call__(self) -> typing.Any:
        self.loop = asyncio.get_running_loop()
        if self.__task is None:
            self.__task = asyncio.create_task(self._init_fixture())
        return await self.__task

    def finalize(self) -> None:
        assert(self.loop is not None)


def pyknic_async_test(decorated_coroutine: typing.Callable[..., typing.Any]) -> typing.Callable[..., typing.Any]:

    def ordinary_fn(original_fn: typing.Callable[..., typing.Any], *args: typing.Any, **kwargs: typing.Any) -> typing.Any:

        async def asynced_fn() -> typing.Any:
            pre_processed_args = [(x if await x() else x) if isinstance(x, BaseAsyncFixture) else x for x in args]
            await original_fn(*pre_processed_args, **kwargs)

        loop = asyncio.get_event_loop()
        return loop.run_until_complete(asynced_fn())

    return decorator(ordinary_fn)(decorated_coroutine)


def async_fixture_generator(
    async_cls: type[BaseAsyncFixture], *args: typing.Any, **kwargs: typing.Any
) -> typing.Callable[..., typing.Any]:

    @pytest.fixture(*args, **kwargs)  # type: ignore[misc]
    def fixture_fn() -> typing.Generator[BaseAsyncFixture, None, None]:
        fixture_object = async_cls()
        yield fixture_object
        fixture_object.finalize()

    return fixture_fn  # type: ignore[no-any-return]
