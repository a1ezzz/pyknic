# -*- coding: utf-8 -*-
# pyknic/lib/fastapi/models/lobby.py
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

# TODO: document the code
# TODO: write tests for the code

import typing

import pydantic


class LobbyArgDescriptor(pydantic.BaseModel):
    arg_type: str


class LobbyPositionalArgs(LobbyArgDescriptor):
    arg_type: typing.Literal['positional'] = pydantic.Field(default='positional', frozen=True)
    values: typing.Tuple[()] = pydantic.Field(default=tuple())


class LobbyKeyWordArgValue(pydantic.BaseModel):
    name: str = pydantic.Field(min_length=1)
    value: int | float | bool | str


class LobbyLobbyKeyWordArgs(pydantic.BaseModel):
    arg_type: typing.Literal['keyword'] = pydantic.Field(default='keyword', frozen=True)
    values: typing.Tuple[()] = pydantic.Field(default=tuple())


class LobbyContextArg(LobbyKeyWordArgValue):
    arg_type: typing.Literal['contextual'] = pydantic.Field(default='contextual', frozen=True)
    values: typing.Tuple[()] = pydantic.Field(default=tuple())


class LobbyCommand(pydantic.BaseModel):
    name: str = pydantic.Field(min_length=1)
    args: LobbyPositionalArgs | None = None
    kwargs: LobbyLobbyKeyWordArgs | None = None
    cargs: LobbyContextArg | None = None
