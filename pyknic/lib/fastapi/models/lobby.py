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


class LobbyKeyWordArgs(pydantic.BaseModel):
    """ This is a base class for default "kwargs" arguments of a command
    """
    pass


class LobbyContextArg(pydantic.BaseModel):
    """ This is a base class for default "cargs" arguments of a command
    """
    pass


class LobbyCommand(pydantic.BaseModel):
    """ This is a lobby command
    """
    model_config = pydantic.ConfigDict(extra='forbid')

    name: str = pydantic.Field(min_length=1, validate_default=True)  # name of a command to execute
    args: typing.Tuple[()] | None = None                             # positional arguments to a command
    kwargs: LobbyKeyWordArgs | None = None                           # kw-arguments to a command
    cargs: LobbyContextArg | None = None                             # context value

    _command_origin: typing.Type[typing.Any] | None = None  # special private class that implements command


class LobbyStrFeedbackResult(pydantic.BaseModel):
    # TODO: there may be predefined properties as the "status" (0 -- command scheduled,
    #  1 -- command completed successfully, 2 -- command completed with error)
    result: str


LobbyCommandResult = typing.Union[NullableResponseModel, LobbyStrFeedbackResult]


class LobbyServerFingerprint(pydantic.BaseModel):
    _fingerprint_bytes: int = 32
    fingerprint: str = pydantic.Field(min_length=44, max_length=44, validate_default=True)  # since it is used in
    # HMAC-SHA256 it must be the same size as 32 bytes (256 bit). In base64 every 3 bytes are encoded with 4 symbols
    # so the target size is 44
