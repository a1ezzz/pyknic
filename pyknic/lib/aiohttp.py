# -*- coding: utf-8 -*-
# pyknic/lib/aiohttp.py
#
# Copyright (C) 2026 the pyknic authors and contributors
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
# TODO: write tests for the code

import typing

import aiohttp


C = typing.TypeVar('C')

async def aiohttp_request(
    request: typing.Callable[[aiohttp.ClientSession], typing.Awaitable[C]],
    session: typing.Optional[aiohttp.ClientSession] = None
) -> C:
    if session is not None:
        return await request(session)

    async with aiohttp.ClientSession() as new_session:
        return await request(new_session)
