# -*- coding: utf-8 -*-
# pyknic/lib/bellboy/app.py
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
from abc import ABCMeta

import aiohttp
import pydantic

from pyknic.lib.bellboy.models import SecretBackendType
from pyknic.lib.bellboy.secret_backend import SecretBackend, KeyringSecretBackendImplementation, SecretTokenModel
from pyknic.lib.bellboy.secret_backend import SharedMemorySecretBackend, SecretBackendImplementationProto
from pyknic.lib.fastapi.lobby import LobbyCommandHandler
from pyknic.lib.fastapi.lobby_fingerprint import LobbyFingerprint
from pyknic.lib.fastapi.headers import FastAPIHeaders
from pyknic.lib.fastapi.models.lobby import LobbyCommandRequest, LobbyFingerprintModel, LobbyCommandResult
from pyknic.lib.registry import APIRegistry, register_api

__default_bellboy_commands_registry__ = APIRegistry()  # default registry for all commands


def register_bellboy_command(
    registry: APIRegistry | None = None,
) -> typing.Callable[..., typing.Any]:
    """This decorator help to register commands with the given registry."""

    if registry is None:
        registry = __default_bellboy_commands_registry__

    return register_api(
        registry=registry,
        api_id=lambda x: x.command_name(),
        callable_api_id=True
    )


class BellboyCLIError(Exception):
    """Indicates errors in Bellboy CLI."""
    pass


class BellBoyCommandHandler(LobbyCommandHandler, metaclass=ABCMeta):
    """ This is an extended version of the :class:`.LobbyCommandHandler`
    """

    @classmethod
    def secret_backend(cls, secret_backend_type: SecretBackendType) -> SecretBackend:
        """ Return a backend implementation by a specified type

        :param secret_backend_type: type of secret backend
        """
        if secret_backend_type == SecretBackendType.keyring:
            secret_backend: SecretBackendImplementationProto = KeyringSecretBackendImplementation()
        elif secret_backend_type == SecretBackendType.shm:
            secret_backend = SharedMemorySecretBackend()
        else:
            raise BellboyCLIError(f'Unknown backend spotted -- {secret_backend_type}')

        return SecretBackend(backend_implementation=secret_backend)

    @classmethod
    def auth_data(cls, secret_backend_type: SecretBackendType, lobby_url: str) -> SecretTokenModel:
        """ Return an auth info for the specified URL from the specified secret backend

        :param secret_backend_type: backend that holds secret
        :param lobby_url: URL which secret should be retrieved
        """
        secret_backend = cls.secret_backend(secret_backend_type)
        all_secrets = secret_backend.get_secrets()

        if lobby_url not in all_secrets.secrets:
            raise BellboyCLIError('Login at first')

        return all_secrets.secrets[lobby_url]


class LobbyClient:
    """This class wraps API calls routine.
    """

    def __init__(self, url: str, fingerprint: typing.Union[LobbyFingerprint | LobbyFingerprintModel], token: str):
        """Create a new client.

        :param url: URL to connect to.
        :param fingerprint: allowed server's fingerprint to check a response
        :param token: token to authenticate with.
        """
        is_lobby_fingerprint = isinstance(fingerprint, LobbyFingerprint)

        self.__url = url
        self.__fingerprint = fingerprint if is_lobby_fingerprint else LobbyFingerprint.from_model(fingerprint)
        self.__token = token

    async def secure_request(
        self,
        fingerprint: LobbyFingerprint,
        session: aiohttp.ClientSession,
        method_name: str,
        path: str | None = None,
        data: str | bytes | None = None
    ) -> bytes:
        """Make a secure request and return bytes that this request returns.

        :param fingerprint: allowed server's fingerprint to check a response
        :param session: HTTP-client to use
        :param method_name: HTTP-method to use (like 'get' or 'post')
        :param path: URL path
        :param data: Data to send with request
        """
        auth_headers = {"Authorization": f"Bearer {self.__token}"}

        session_method = getattr(session, method_name)
        async with session_method(f'{self.__url}{path if path else ""}', headers=auth_headers, data=data) as response:
            if response.status != 200:
                raise BellboyCLIError(f'API request failed with status code {response.status}')

            binary_body = await response.content.read()
            signature = fingerprint.sign(binary_body, encode_base64=True).decode('ascii')

            if response.headers[FastAPIHeaders.fingerprint.value] != signature:
                raise BellboyCLIError(
                    'Response signature mismatch! Consider to restart session and validate connectivity'
                )
            return binary_body  # type: ignore[no-any-return]

    async def command_request(
        self, command: LobbyCommandRequest, session: typing.Optional[aiohttp.ClientSession] = None
    ) -> LobbyCommandResult:
        """Send command to a server.
        :param command: Command to send to a server
        :param session: HTTP-client to use (a new session will be made if this parameter is omitted)
        """

        async def cmd_request(s: aiohttp.ClientSession) -> LobbyCommandResult:
            request_json = command.model_dump_json()
            result = await self.secure_request(
                self.__fingerprint, s, 'post', data=request_json  # type: ignore[arg-type]
            )
            return pydantic.TypeAdapter(LobbyCommandResult).validate_json(result.decode())

        if session:
            return await cmd_request(session)

        async with aiohttp.ClientSession() as new_session:
            return await cmd_request(new_session)

    @staticmethod
    async def fingerprint(url: str, session: typing.Optional[aiohttp.ClientSession] = None) -> LobbyFingerprint:
        """Return server's fingerprint.

        :param url: URL to connect to.
        :param session: HTTP-client to use
        """
        # TODO: persist it from a server side

        async def fp_by_session(s: aiohttp.ClientSession) -> LobbyFingerprint:
            async with s.get(f'{url}/fingerprint') as response:

                if response.status != 200:
                    raise BellboyCLIError('Unable to fetch fingerprint')

                fingerprint_model = LobbyFingerprintModel.model_validate(await response.json())
                return LobbyFingerprint.deserialize(fingerprint_model.fingerprint.encode('ascii'))

        if session is not None:
            return await fp_by_session(session)

        async with aiohttp.ClientSession() as new_session:
            return await fp_by_session(new_session)
