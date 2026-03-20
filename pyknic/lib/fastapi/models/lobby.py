# -*- coding: utf-8 -*-
# pyknic/lib/fastapi/models/lobby.py
#
# Copyright (C) 2025-2026 the pyknic authors and contributors
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

from pyknic.lib.fastapi.models.base import NullableModel
from pyknic.lib.fastapi.lobby_fingerprint import LobbyFingerprint
from pyknic.version import __version__


class LobbyCommandRequest(pydantic.BaseModel):
    """ This is a request for a command execution
    """
    model_config = pydantic.ConfigDict(extra='forbid')  # just to be sure that everything attributes are known
    client_version: str = __version__                   # a description of a client
    name: str                                           # a command to execute
    args: typing.Dict[str, typing.Any]                  # command's arguments (dictionary may be empty)


class LobbyStrFeedbackResult(pydantic.BaseModel):
    """Possible command result -- as a string"""
    model_config = pydantic.ConfigDict(extra='forbid')  # just to be sure that everything attributes are known
    server_version: str = __version__                   # a description of a server
    str_result: str                                     # a command result


class LobbyKeyValueFeedbackResult(pydantic.BaseModel):
    """Possible command result -- as a key-value pairs"""
    model_config = pydantic.ConfigDict(extra='forbid')  # just to be sure that everything attributes are known
    server_version: str = __version__                   # a description of a server
    kv_result: typing.Dict[str, typing.Any]             # a command result


class LobbyListValueFeedbackResult(pydantic.BaseModel):
    """Possible command result -- as a list of values"""
    model_config = pydantic.ConfigDict(extra='forbid')  # just to be sure that everything attributes are known
    server_version: str = __version__                   # a description of a server
    list_result: typing.List[typing.Any]                # a command result


# possible command results
LobbyCommandResult = typing.Union[
    NullableModel, LobbyStrFeedbackResult, LobbyKeyValueFeedbackResult, LobbyListValueFeedbackResult
]


class LobbyFingerprintModel(pydantic.BaseModel):
    """ A fingerprint of a lobby server
    """
    fingerprint: str = pydantic.Field(  # unique string. This is a string because of min/max length limitations
        min_length=LobbyFingerprint.serialized_length(),
        max_length=LobbyFingerprint.serialized_length(),
        validate_default=True
    )
