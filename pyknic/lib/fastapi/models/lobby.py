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

import typing

import pydantic

from pyknic.lib.fastapi.models.base import NullableResponseModel
from pyknic.lib.fastapi.lobby_fingerprint import LobbyFingerprint


class LobbyCommand(pydantic.BaseModel):
    """ This is a lobby command
    """
    model_config = pydantic.ConfigDict(extra='forbid')

    name: str = pydantic.Field(min_length=1, validate_default=True)  # name of a command to execute
    args: typing.Tuple[()] | None = None                             # positional arguments to a command
    kwargs: None = None                                              # kw-arguments to a command
    cargs: None = None                                               # context value

    _command_origin: typing.Type[typing.Any] | None = None  # special private class that implements command


class LobbyCommandRequest(LobbyCommand):
    args: typing.Tuple[typing.Any, ...] | None = None  # positional arguments to a command
    kwargs: typing.Any | None = None                   # kw-arguments to a command
    cargs: typing.Any | None = None                    # context value


class LobbyStrFeedbackResult(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(extra='forbid')
    str_result: str


class LobbyKeyValueFeedbackResult(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(extra='forbid')
    kv_result: typing.Dict[str, typing.Any]


LobbyCommandResult = typing.Union[NullableResponseModel, LobbyStrFeedbackResult, LobbyKeyValueFeedbackResult]


class LobbyServerFingerprint(pydantic.BaseModel):
    fingerprint: str = pydantic.Field(
        min_length=LobbyFingerprint.serialized_length(),
        max_length=LobbyFingerprint.serialized_length(),
        validate_default=True
    )
