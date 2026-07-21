# -*- coding: utf-8 -*-

import asyncio
import contextlib
import os
import pytest
import typing

import aiohttp
import jwt
import pydantic

from pyknic.lib.bellboy.app import BellBoyCommandHandler, BellboyCLIError, LobbyClient, LobbyClientAuth
from pyknic.lib.bellboy.models import SecretBackendType
from pyknic.lib.bellboy.secret_backend import SecretBackend, SharedMemorySecretBackend, SecretTokenModel
from pyknic.lib.crypto.rsa import RSAPrivateKey, InvalidSignature
from pyknic.lib.fastapi.lobby import LobbyCommandHandler
from pyknic.lib.fastapi.models.base import NullableModel
from pyknic.lib.fastapi.models.lobby import LobbyCommandResult, LobbyCommandRequest, LobbyEncodedJWT
from pyknic.lib.fastapi.models.lobby import LobbyPublicKeyModel
from pyknic.lib.gettext import GetTextWrapper
from pyknic.tasks.fastapi.lobby import LobbyApp

from fixtures.asyncio import pyknic_async_test
from fixtures.fastapi import AsyncFastAPIFixture


def test_exception() -> None:
    assert(issubclass(BellboyCLIError, Exception))


class TestBellBoyCommandHandler:

    class CMD(BellBoyCommandHandler):

        @classmethod
        def command_name(cls) -> str:
            return "test"

        @classmethod
        def command_model(cls) -> typing.Type[pydantic.BaseModel]:
            return NullableModel

        async def exec(self) -> LobbyCommandResult:
            return NullableModel()

    @pyknic_async_test
    async def test(self, module_event_loop: asyncio.AbstractEventLoop) -> None:
        assert(issubclass(BellBoyCommandHandler, LobbyCommandHandler))

        cmd_object = TestBellBoyCommandHandler.CMD.prepare_command(NullableModel())
        await cmd_object.exec()

    @pytest.mark.parametrize('backend_type, enable_test', [
        [SecretBackendType.keyring, 'DBUS_SESSION_BUS_ADDRESS' in os.environ],
        [SecretBackendType.shm, True]
    ])
    def test_secret_backend(self, backend_type: SecretBackendType, enable_test: bool) -> None:
        if enable_test:
            backend = BellBoyCommandHandler.secret_backend(backend_type)
            assert(isinstance(backend, SecretBackend))

    def test_auth_data(self) -> None:
        lobby_url = "unknown-proto://in?lid-hostname:700O0/?"

        with pytest.raises(BellboyCLIError):
            _ = BellBoyCommandHandler.auth_data(SecretBackendType.shm, lobby_url)

        backend = SecretBackend(SharedMemorySecretBackend())

        try:
            private_key = RSAPrivateKey.generate(1024)

            lobby_pub_key = LobbyPublicKeyModel(
                pem=private_key.public_key().export_pem().decode('ascii'),
                sign_hash_method='some-hash'
            )
            jwt = LobbyEncodedJWT(token_data='invalid-token')

            backend.set_secret(lobby_url, lobby_pub_key, jwt)

            result = BellBoyCommandHandler.auth_data(SecretBackendType.shm, lobby_url)

            assert(isinstance(result, SecretTokenModel))
            assert(result.public_key.sign_hash_method == 'some-hash')
            assert(result.jwt_token.token_data == 'invalid-token')
        finally:
            # there is no need to dedicated fixture
            with contextlib.suppress(KeyError):
                backend.pop_secret(lobby_url)

    def test_create_client(self) -> None:
        lobby_url = "unknown-proto://in?lid-hostname:700O0/?"

        with pytest.raises(BellboyCLIError):
            _ = BellBoyCommandHandler.auth_data(SecretBackendType.shm, lobby_url)

        backend = SecretBackend(SharedMemorySecretBackend())

        try:
            private_key = RSAPrivateKey.generate(1024)

            lobby_pub_key = LobbyPublicKeyModel(
                pem=private_key.public_key().export_pem().decode('ascii'),
                sign_hash_method='some-hash'
            )
            jwt = LobbyEncodedJWT(token_data='invalid-token')

            backend.set_secret(lobby_url, lobby_pub_key, jwt)
            client = BellBoyCommandHandler.create_client(SecretBackendType.shm, lobby_url)

            assert(isinstance(client, LobbyClient))
            assert(client.jwt_token().token_data == 'invalid-token')
            assert(client.lobby_public_key().sign_hash_method == 'some-hash')
            assert(client.lobby_public_key().pem == lobby_pub_key.pem)
            assert(client.public_key().export_pem().decode('ascii') == lobby_pub_key.pem)
        finally:
            # there is no need to dedicated fixture
            with contextlib.suppress(KeyError):
                backend.pop_secret(lobby_url)


class TestLobbyClient:

    __lobby_yaml__ = """
        pyknic:
            fastapi:
                lobby:
                    aaa_policies:
                        allow_all:
                            handler: trust  # no auth!
                            handler_settings:
                                as_user: 'admin'
                            allowed_commands: []  # list of allowed commands
                            denied_commands: []  # list of denied commands
        """

    @AsyncFastAPIFixture.base_config(LobbyApp, __lobby_yaml__)
    @pyknic_async_test
    async def test_public_key(
        self,
        module_event_loop: asyncio.AbstractEventLoop,
        fastapi_module_fixture: AsyncFastAPIFixture,
        gettext: GetTextWrapper
    ) -> None:
        lobby_path = fastapi_module_fixture.app_config["pyknic"]["fastapi"]["lobby"]["main_url_path"]
        lobby_url = f'http://localhost:8000{lobby_path}'

        async with aiohttp.ClientSession() as session:
            client_auth = LobbyClientAuth(lobby_url, session)
            lobby_public_key = await client_auth.lobby_public_key()
            assert(isinstance(lobby_public_key, LobbyPublicKeyModel))

        client_auth = LobbyClientAuth(lobby_url)
        lobby_public_key = await client_auth.lobby_public_key()
        assert(isinstance(lobby_public_key, LobbyPublicKeyModel))

    @AsyncFastAPIFixture.base_config(LobbyApp, __lobby_yaml__)
    @pyknic_async_test
    async def test_ping(
        self,
        module_event_loop: asyncio.AbstractEventLoop,
        fastapi_module_fixture: AsyncFastAPIFixture,
        gettext: GetTextWrapper
    ) -> None:
        lobby_path = fastapi_module_fixture.app_config["pyknic"]["fastapi"]["lobby"]["main_url_path"]
        lobby_url = f'http://localhost:8000{lobby_path}'

        client_auth = LobbyClientAuth(lobby_url)
        client = await client_auth.login_with_trust()

        ping_request = LobbyCommandRequest(name='ping', args=NullableModel().model_dump(), plugin_version='test-plugin')

        async with aiohttp.ClientSession() as session:
            result = await client.command_request(ping_request, session=session)
            assert(len(result.str_result) > 0)  # type: ignore[union-attr]

        invalid_client = LobbyClient(lobby_url, client.lobby_public_key(), LobbyEncodedJWT(token_data='invalid-token'))
        with pytest.raises(BellboyCLIError):
            await invalid_client.command_request(ping_request)

    @AsyncFastAPIFixture.base_config(LobbyApp, __lobby_yaml__)
    @pyknic_async_test
    async def test_invalid_signature_error(
        self,
        module_event_loop: asyncio.AbstractEventLoop,
        fastapi_module_fixture: AsyncFastAPIFixture,
        gettext: GetTextWrapper
    ) -> None:
        lobby_path = fastapi_module_fixture.app_config["pyknic"]["fastapi"]["lobby"]["main_url_path"]
        lobby_url = f'http://localhost:8000{lobby_path}'

        invalid_private_key = RSAPrivateKey.generate(1024)

        client_auth = LobbyClientAuth(lobby_url)
        client = await client_auth.login_with_trust()

        invalid_client = LobbyClient(
            lobby_url,
            LobbyPublicKeyModel(
                pem=invalid_private_key.public_key().export_pem().decode(),
                sign_hash_method='sha256'
            ),
            client.jwt_token()
        )

        ping_request = LobbyCommandRequest(name='ping', args=NullableModel().model_dump(), plugin_version='test-plugin')

        with pytest.raises(InvalidSignature):
            await invalid_client.command_request(ping_request)


class TestLobbyClientAuth:

    __trust_lobby_yaml__ = """
        pyknic:
            fastapi:
                lobby:
                    aaa_policies:
                        allow_all:
                            handler: trust  # no auth!
                            handler_settings:
                                as_user: 'admin'
                            allowed_commands: []  # list of allowed commands
                            denied_commands: []  # list of denied commands
        """

    __token_lobby_yaml__ = """
        pyknic:
            fastapi:
                lobby:
                    aaa_policies:
                        allow_all:
                            handler: bearer_static_token
                            handler_settings:
                                secret_token: 'secret-token'
                                as_user: 'admin'
                            allowed_commands: []  # list of allowed commands
                            denied_commands: []  # list of denied commands
        """

    __password_lobby_yaml__ = """
        pyknic:
            fastapi:
                lobby:
                    aaa_policies:
                        allow_all:
                            handler: inline_htpasswd
                            handler_settings:
                                credentials:
                                    - 'foo:$2y$05$Z7/3diNsWaUZ1JtEqQRdu.78F86tPEzPn/nEBTSVVyIugQtkAyRVK'
                            allowed_commands: []  # list of allowed commands
                            denied_commands: []  # list of denied commands
        """

    @AsyncFastAPIFixture.base_config(LobbyApp, __trust_lobby_yaml__)
    @pyknic_async_test
    async def test_invalid_jwt(
        self,
        module_event_loop: asyncio.AbstractEventLoop,
        fastapi_module_fixture: AsyncFastAPIFixture,
        lobby_shm_secrets: typing.Callable[[str, str], typing.Coroutine[None, None, None]]
    ) -> None:
        lobby_path = fastapi_module_fixture.app_config["pyknic"]["fastapi"]["lobby"]["main_url_path"]
        lobby_url = f'http://localhost:8000{lobby_path}'

        client_auth = LobbyClientAuth(lobby_url)
        await client_auth.lobby_public_key()

        custom_private_key = RSAPrivateKey.generate(1024)
        pub_key = custom_private_key.public_key()
        pub_pem = pub_key.export_pem().decode('ascii')
        client_auth._LobbyClientAuth__public_key = pub_key  # type: ignore[attr-defined]  # just a test
        client_auth._LobbyClientAuth__lobby_public_key.pem = pub_pem  # type: ignore[attr-defined]  # just a test

        with pytest.raises(jwt.DecodeError):
            # public key is different
            await client_auth.login_with_trust()

    @AsyncFastAPIFixture.base_config(LobbyApp, __token_lobby_yaml__)
    @pyknic_async_test
    async def test_login_with_token(
        self,
        module_event_loop: asyncio.AbstractEventLoop,
        fastapi_module_fixture: AsyncFastAPIFixture,
        lobby_shm_secrets: typing.Callable[[str, str], typing.Coroutine[None, None, None]]
    ) -> None:
        lobby_path = fastapi_module_fixture.app_config["pyknic"]["fastapi"]["lobby"]["main_url_path"]
        lobby_url = f'http://localhost:8000{lobby_path}'

        client_auth = LobbyClientAuth(lobby_url)

        with pytest.raises(BellboyCLIError):
            # no more trust
            _ = await client_auth.login_with_trust()

        _ = await client_auth.login_with_token('secret-token')  # this is ok

        with pytest.raises(BellboyCLIError):
            # invalid token
            _ = await client_auth.login_with_token('invalid-token')

    @AsyncFastAPIFixture.base_config(LobbyApp, __password_lobby_yaml__)
    @pyknic_async_test
    async def test_login_with_basic(
        self,
        module_event_loop: asyncio.AbstractEventLoop,
        fastapi_module_fixture: AsyncFastAPIFixture,
        lobby_shm_secrets: typing.Callable[[str, str], typing.Coroutine[None, None, None]]
    ) -> None:
        lobby_path = fastapi_module_fixture.app_config["pyknic"]["fastapi"]["lobby"]["main_url_path"]
        lobby_url = f'http://localhost:8000{lobby_path}'

        client_auth = LobbyClientAuth(lobby_url)

        with pytest.raises(BellboyCLIError):
            # no more trust
            _ = await client_auth.login_with_trust()

        _ = await client_auth.login_with_basic('foo', 'bar')  # this is ok

        with pytest.raises(BellboyCLIError):
            # invalid password
            _ = await client_auth.login_with_basic('user', 'invalid-pass')
