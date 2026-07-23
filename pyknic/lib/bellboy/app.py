# -*- coding: utf-8 -*-
# pyknic/lib/bellboy/app.py
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

import base64
import typing
from abc import ABCMeta

import aiohttp
import jwt
import pydantic

from pyknic.lib.aiohttp import aiohttp_request
from pyknic.lib.bellboy.models import SecretBackendType
from pyknic.lib.bellboy.secret_backend import SecretBackend, KeyringSecretBackendImplementation, SecretTokenModel
from pyknic.lib.bellboy.secret_backend import SharedMemorySecretBackend, SecretBackendImplementationProto
from pyknic.lib.crypto.rsa import RSAPublicKey
from pyknic.lib.fastapi.lobby import LobbyCommandHandler, URLPath
from pyknic.lib.fastapi.headers import FastAPIHeaders
from pyknic.lib.fastapi.models.lobby import LobbyCommandRequest, LobbyCommandResult, LobbyPublicKeyModel
from pyknic.lib.fastapi.models.lobby import LobbyEncodedJWT
from pyknic.lib.registry import APIRegistry, register_api
from pyknic.lib.log import Logger


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

    @classmethod
    def create_client(cls, secret_backend_type: SecretBackendType, lobby_url: str) -> 'LobbyClient':
        """ Retrieve an auth info and create a client

        :param secret_backend_type: backend that holds secret
        :param lobby_url: URL which secret should be retrieved
        """
        auth_data = cls.auth_data(secret_backend_type, lobby_url)
        return LobbyClient(lobby_url, auth_data.public_key, auth_data.jwt_token)


class LobbyClient:
    """This class wraps API calls routine.
    """

    def __init__(self, url: str, lobby_public_key: LobbyPublicKeyModel, jwt_token: LobbyEncodedJWT):
        """Create a new client.

        :param url: URL to connect to.
        :param lobby_public_key: public key information tha has been received from a server
        :param jwt_token: authentication token
        """

        self.__url = url
        self.__lobby_public_key = lobby_public_key
        self.__public_key = RSAPublicKey.import_pem(lobby_public_key.pem.encode('ascii'))
        self.__sign_hash_method = lobby_public_key.sign_hash_method
        self.__jwt_token = jwt_token

    def jwt_token(self) -> LobbyEncodedJWT:
        """ Return JWT that is used by this client
        """
        return self.__jwt_token

    def public_key(self) -> RSAPublicKey:
        """ Return public key this client is used for data verification
        """
        return self.__public_key

    def lobby_public_key(self) -> LobbyPublicKeyModel:
        """ Return public key and signing method this client is used for data verification
        """
        return self.__lobby_public_key

    async def secure_request(
        self,
        session: aiohttp.ClientSession,
        method_name: str,
        path: str | None = None,
        data: str | bytes | None = None
    ) -> bytes:
        """Make a secure request and return bytes that this request returns.

        :param session: HTTP-client to use
        :param method_name: HTTP-method to use (like 'get' or 'post')
        :param path: URL path
        :param data: Data to send with request
        """
        headers = {
            "Authorization": f"Bearer {self.__jwt_token.token_data}",
            "Content-Type": "application/json",
        }

        session_method = getattr(session, method_name)
        async with session_method(f'{self.__url}{path if path else ""}', headers=headers, data=data) as response:
            if response.status != 200:
                raise BellboyCLIError(f'API request failed with status code {response.status}')

            binary_body: bytes = await response.content.read()

            sign_str = response.headers[FastAPIHeaders.signature.value]
            sign_bin = base64.b64decode(sign_str)

            self.__public_key.verify(sign_bin, binary_body, self.__sign_hash_method)

            return binary_body

    async def command_request(
        self, command: LobbyCommandRequest, session: typing.Optional[aiohttp.ClientSession] = None
    ) -> LobbyCommandResult:
        """Send command to a server.
        :param command: Command to send to a server
        :param session: HTTP-client to use (a new session will be made if this parameter is omitted)
        """

        async def cmd_request(s: aiohttp.ClientSession) -> LobbyCommandResult:
            request_json = command.model_dump_json()
            result = await self.secure_request(s, 'post', data=request_json)
            return pydantic.TypeAdapter(LobbyCommandResult).validate_json(result.decode())

        return await aiohttp_request(cmd_request, session)


class LobbyClientAuth:
    """ This class helps to authenticate a client on a remote lobby server.
    """

    def __init__(
        self,
        url: str,
        session: typing.Optional[aiohttp.ClientSession] = None,
        jwt_algorithm: typing.Optional[str] = None
    ):
        """Create an authentication handler

        :param url: remote lobby URL
        :param session: aiohttp session to use for HTTP-requests
        :param jwt_algorithm: JWT algorithm to use (RS256 is used by default)
        """
        self.__url = url
        self.__session = session
        self.__jwt_algorithm = jwt_algorithm if jwt_algorithm else 'RS256'

        self.__lobby_public_key: typing.Optional[LobbyPublicKeyModel] = None
        self.__public_key: typing.Optional[RSAPublicKey] = None

    async def lobby_public_key(self) -> LobbyPublicKeyModel:
        """ Fetch and return server's public key. Public key is retrieved only once, later call will return
        cached value
        """

        if self.__lobby_public_key is not None:
            return self.__lobby_public_key

        async def pk_by_session(s: aiohttp.ClientSession) -> LobbyPublicKeyModel:
            async with s.get(f'{self.__url}/{URLPath.public_key.value}') as response:

                if response.status != 200:
                    raise BellboyCLIError('Unable to fetch public key')

                self.__lobby_public_key = LobbyPublicKeyModel.model_validate(await response.json())
                self.__public_key = RSAPublicKey.import_pem(self.__lobby_public_key.pem.encode('ascii'))
                assert(self.__lobby_public_key)
                return self.__lobby_public_key

        return await aiohttp_request(pk_by_session, self.__session)

    async def __encoded_jwt(self, dict_obj: typing.Dict[str, typing.Any]) -> LobbyEncodedJWT:
        """ Parse a json-a-like object into JWT, verify it and return it

        :param dict_obj: object to parse
        """

        if self.__public_key is None:
            await self.lobby_public_key()
        assert(self.__public_key is not None)

        encoded_jwt = LobbyEncodedJWT.model_validate(dict_obj)

        try:
            # just to check signature
            _ = jwt.decode(
                encoded_jwt.token_data,
                self.__public_key.export_pem(),
                algorithms=[self.__jwt_algorithm],
                options={"verify_aud": False}  # this is OK, since we check signature
            )

        except jwt.DecodeError as e:
            Logger.error(f'Unable to decode a JWT -- {e}')
            raise

        return encoded_jwt

    async def __client_by_jwt(self, jwt_token: LobbyEncodedJWT) -> LobbyClient:
        """ Create a :class:`.LobbyClient` instance by JWT

        :param jwt_token: lobby's credential
        """
        return LobbyClient(
            self.__url,
            await self.lobby_public_key(),
            jwt_token
        )

    async def login_with_trust(self) -> LobbyClient:
        """ Try to authenticate with "trust" method
        """

        async def get_jwt(s: aiohttp.ClientSession) -> LobbyEncodedJWT:
            async with s.post(f'{self.__url}/{URLPath.login_trust.value}') as response:
                if response.status != 200:
                    raise BellboyCLIError('Unable to authorize with the "trust" method!')

                return await self.__encoded_jwt(await response.json())

        jwt_token = await aiohttp_request(get_jwt, self.__session)
        return await self.__client_by_jwt(jwt_token)

    async def login_with_token(self, secret: str) -> LobbyClient:
        """ Try to authenticate with a beacon
        """

        async def get_jwt(s: aiohttp.ClientSession) -> LobbyEncodedJWT:
            auth_headers = {"Authorization": f"Bearer {secret}"}

            async with s.post(f'{self.__url}/{URLPath.login_bearer.value}', headers=auth_headers) as response:
                if response.status != 200:
                    raise BellboyCLIError('Unable to authorize with the "token" method!')

                return await self.__encoded_jwt(await response.json())

        jwt_token = await aiohttp_request(get_jwt, self.__session)
        return await self.__client_by_jwt(jwt_token)

    async def login_with_basic(self, login: str, secret: str) -> LobbyClient:
        """ Try to authenticate with login and password
        """

        async def get_jwt(s: aiohttp.ClientSession) -> LobbyEncodedJWT:

            async with s.post(
                f'{self.__url}/{URLPath.login_basic.value}',
                auth=aiohttp.BasicAuth(login, secret)
            ) as response:
                if response.status != 200:
                    raise BellboyCLIError('Unable to authorize with the "basic" method!')

                return await self.__encoded_jwt(await response.json())

        jwt_token = await aiohttp_request(get_jwt, self.__session)
        return await self.__client_by_jwt(jwt_token)
