# -*- coding: utf-8 -*-
# pyknic/lib/integrated_commands/login.py
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

# TODO: check that the public key does not changed! Store it like a known hosts!

import enum
import os
import typing

import pydantic
import pydantic_settings

from pyknic.lib.bellboy.app import register_bellboy_command, BellBoyCommandHandler, LobbyClientAuth
from pyknic.lib.bellboy.models import RequiredMainBellBoyCommandModel
from pyknic.lib.fastapi.models.lobby import LobbyCommandResult, LobbyCommandRequest, LobbyStrFeedbackResult
from pyknic.lib.integrated_commands.ping import LobbyPingCommand

from pyknic.lib.integrated_commands.commands_version import __plugin_version__


@enum.unique
class AuthenticationMode(enum.Enum):
    trust = 'trust'
    token = 'token'
    basic = 'basic'


class SecretReadModel(pydantic_settings.CliMutuallyExclusiveGroup):

    model_config = pydantic.ConfigDict(extra='forbid')

    direct: typing.Optional[str] = pydantic.Field(
        default=None,
        description='A secret is submitted with this argument directly'
    )

    file: typing.Optional[str] = pydantic.Field(
        default=None,
        description='A secret is stored inside a file this argument points to'
    )

    env_var: typing.Optional[str] = pydantic.Field(
        validation_alias=pydantic.AliasChoices('env-var'),
        default=None,
        description='A secret is stored within an environment variable this argument points to'
    )


class LoginCommandModel(RequiredMainBellBoyCommandModel):

    authentication: AuthenticationMode = pydantic.Field(
        validation_alias=pydantic.AliasChoices('a', 'authentication'),
        description='specifies a way this client will be authenticated on a lobby server'
    )

    login: typing.Optional[str] = pydantic.Field(description='login', default=None)
    secret: typing.Optional[SecretReadModel] = pydantic.Field(description='authentication secret', default=None)


@register_bellboy_command()
class LoginCommand(BellBoyCommandHandler):
    """Login to a custom lobby server
    """

    __max_secret_file_size__ = 1024

    @classmethod
    def command_name(cls) -> str:
        """The :meth:`.BellBoyCommandHandler.command_name` method implementation"""
        return "login"

    @classmethod
    def command_model(cls) -> typing.Type[pydantic.BaseModel]:
        """The :meth:`.BellBoyCommandHandler.command_model` method implementation"""
        return LoginCommandModel

    def __read_secret(self) -> str:
        assert(isinstance(self._args, LoginCommandModel))

        if self._args.secret is None:
            raise ValueError('A secret is required!')

        if self._args.secret.direct is not None:
            return self._args.secret.direct
        elif self._args.secret.file is not None:
            with open(self._args.secret.file, 'r') as f:
                secret_data = f.read(self.__max_secret_file_size__)
                if len(secret_data) < self.__max_secret_file_size__:
                    return secret_data
                elif len(secret_data) == self.__max_secret_file_size__ and len(f.read(1)) == 0:
                    return secret_data

                raise ValueError(f'Unable to read a secret from the file "{self._args.secret.file}"!')

        elif self._args.secret.env_var is not None:
            return os.environ[self._args.secret.env_var]

        raise ValueError('Unable to read a secret!')

    async def exec(self) -> LobbyCommandResult:
        """The :meth:`.BellBoyInternalCommand.exec_from_cli` method implementation
        """
        assert(isinstance(self._args, LoginCommandModel))

        if self._args.authentication == AuthenticationMode.trust:
            if self._args.login is not None or self._args.secret is not None:
                raise ValueError('A login and/or secret were submitted for the "trust" method')
        elif self._args.authentication == AuthenticationMode.token:
            if self._args.login is not None or self._args.secret is None:
                raise ValueError('A login was submitted and/or secret was not set for the "token" method')
        else:
            assert(self._args.authentication == AuthenticationMode.basic)
            if self._args.login is None or self._args.secret is None:
                raise ValueError('A login and/or secret were not set for the "basic" method')

        client_auth = LobbyClientAuth(self._args.server.lobby_url)

        test_client = None
        if self._args.authentication == AuthenticationMode.trust:
            test_client = await client_auth.login_with_trust()
        elif self._args.authentication == AuthenticationMode.token:
            secret = self.__read_secret()
            test_client = await client_auth.login_with_token(secret)
        else:
            assert(self._args.authentication == AuthenticationMode.basic)
            assert(self._args.login)
            secret = self.__read_secret()
            test_client = await client_auth.login_with_basic(self._args.login, secret)

        assert(test_client is not None)

        # just to check that auth is ok
        await test_client.command_request(
            LobbyCommandRequest(
                name=LobbyPingCommand.command_name(),
                args=LobbyPingCommand.command_model()().model_dump(),
                plugin_version=__plugin_version__
            )
        )

        secret_backend = self.secret_backend(self._args.server.secret_backend)
        secret_backend.set_secret(self._args.server.lobby_url, test_client.lobby_public_key(), test_client.jwt_token())
        return LobbyStrFeedbackResult(
            str_result=f'Successful login to the {self._args.server.lobby_url}',
            plugin_version=__plugin_version__
        )
