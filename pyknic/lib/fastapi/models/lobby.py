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

import datetime
import typing
import uuid

import pydantic

from pyknic.lib.fastapi.models.base import NullableModel
from pyknic.version import __version__


class LobbyCommandRequest(pydantic.BaseModel):
    """ This is a request for a command execution
    """
    model_config = pydantic.ConfigDict(extra='forbid')  # just to be sure that everything attributes are known
    client_version: str = __version__                   # a description of a client that sends a request
    plugin_version: str                                 # a version of a plugin that created this request
    name: str                                           # a command to execute
    args: typing.Dict[str, typing.Any]                  # command's arguments (dictionary may be empty)


class LobbyStrFeedbackResult(pydantic.BaseModel):
    """Possible command result -- as a string"""
    model_config = pydantic.ConfigDict(extra='forbid')  # just to be sure that everything attributes are known
    server_version: str = __version__                   # a description of a server that receives a request
    plugin_version: str                                 # a version of a plugin that processed a request
    str_result: str                                     # a command result


class LobbyKeyValueFeedbackResult(pydantic.BaseModel):
    """Possible command result -- as a key-value pairs"""
    model_config = pydantic.ConfigDict(extra='forbid')  # just to be sure that everything attributes are known
    server_version: str = __version__                   # a description of a server that receives a request
    plugin_version: str                                 # a version of a plugin that processed a request
    kv_result: typing.Dict[str, typing.Any]             # a command result


class LobbyListValueFeedbackResult(pydantic.BaseModel):
    """Possible command result -- as a list of values"""
    model_config = pydantic.ConfigDict(extra='forbid')  # just to be sure that everything attributes are known
    server_version: str = __version__                   # a description of a server that receives a request
    plugin_version: str                                 # a version of a plugin that processed a request
    list_result: typing.List[typing.Any]                # a command result


# possible command results
LobbyCommandResult = typing.Union[
    NullableModel, LobbyStrFeedbackResult, LobbyKeyValueFeedbackResult, LobbyListValueFeedbackResult
]


class LobbyPublicKeyModel(pydantic.BaseModel):
    """ This model represents a public key """
    model_config = pydantic.ConfigDict(extra='forbid')  # just to be sure that everything attributes are known

    pem: str  # RSA public key in PEM container


class LobbyEncodedJWT(pydantic.BaseModel):
    """ This model represents an encoded JWT """

    model_config = pydantic.ConfigDict(extra='forbid')  # just to be sure that everything attributes are known

    token_data: str  # encoded JWT


class LobbyJWTPayload(pydantic.BaseModel):
    """ This model represents a JWT as it is

    Known JWT names:
      - https://en.wikipedia.org/wiki/JSON_Web_Token#Standard_fields
      - https://pyjwt.readthedocs.io/en/latest/usage.html#registered-claim-names
    JWT and FastAPI:
      - https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/#handle-jwt-tokens
    """

    model_config = pydantic.ConfigDict(extra='forbid')  # just to be sure that everything attributes are known

    # known JWT fields:
    sub: typing.Union[str, int]                          # subject claim
    exp: int                                             # expiration time claim
    iat: int                                             # issued at claim
    iss: str                                             # issuer claim
    aud: str                                             # audience claim
    jti: typing.Optional[typing.Union[str, int]] = None  # JWT id claim

    # lobby-specific fields:
    policy_name: str                                     # name of an AAA policy that issued this token
    # TODO: may be a single jti is better than policy_name

    @classmethod
    def generate(
        cls,
        ttl: int,
        subject: typing.Union[str, int],
        policy_name: str,
        lobby_host: str,
        lobby_port: int,
        audience: str
    ) -> 'LobbyJWTPayload':
        """ Create a JWT

        :param ttl: when this token will be expired
        :param subject: subject claim
        :param policy_name: name of an AAA policy that issued this token
        :param lobby_host: is used for the "iss" generation (same as the "lobby_host"
        in the :meth:`.LobbyJWTPayload.issuer` method)
        :param lobby_port: is used for the "iss" generation (same as the "lobby_port"
        in the :meth:`.LobbyJWTPayload.issuer` method)
        :param audience: audience claim
        """

        now = int(datetime.datetime.now().timestamp())

        return LobbyJWTPayload(
            iat=now,
            exp=now + ttl,
            iss=cls.issuer(lobby_host, lobby_port),
            aud=audience,
            jti=str(uuid.uuid4()),
            sub=subject,
            policy_name=policy_name
        )

    @classmethod
    def issuer(cls, lobby_host: str, lobby_port: int) -> str:
        """ Generate the "iss" (issuer claim)

        :param lobby_host: a host that this server is listening on
        :param lobby_port: a port that this server is listening on
        """
        return f'urn:lobby:{lobby_host}:{lobby_port}'
