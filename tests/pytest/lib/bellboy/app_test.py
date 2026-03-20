# -*- coding: utf-8 -*-

import asyncio
import contextlib
import os
import pytest
import typing

import aiohttp
import pydantic

from pyknic.lib.bellboy.app import BellBoyCommandHandler, BellboyCLIError, LobbyClient
from pyknic.lib.bellboy.models import SecretBackendType
from pyknic.lib.bellboy.secret_backend import SecretBackend
from pyknic.lib.fastapi.lobby import LobbyCommandHandler
from pyknic.lib.fastapi.lobby_fingerprint import LobbyFingerprint
from pyknic.lib.fastapi.models.base import NullableModel
from pyknic.lib.fastapi.models.lobby import LobbyCommandResult, LobbyCommandRequest
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

        backend = BellBoyCommandHandler.secret_backend(SecretBackendType.shm)

        try:
            fingerprint = LobbyFingerprint.generate_fingerprint()
            token = 'secret-token'

            backend.set_secret(lobby_url, fingerprint, token)
            result = BellBoyCommandHandler.auth_data(SecretBackendType.shm, lobby_url)
            assert(result.server_fingerprint.fingerprint == str(fingerprint))
            assert(result.token == token)
        finally:
            # there is no need to dedicated fixture
            with contextlib.suppress(KeyError):
                backend.pop_secret(lobby_url)


class TestLobbyClient:

    __secret_token__ = 'secret-token'
    __secret_token_yaml__ = f"""
    pyknic:
        fastapi:
            lobby:
                secret_token: {__secret_token__}
    """

    @AsyncFastAPIFixture.base_config(LobbyApp, __secret_token_yaml__)
    @pyknic_async_test
    async def test_fingerprint(
        self,
        module_event_loop: asyncio.AbstractEventLoop,
        fastapi_module_fixture: AsyncFastAPIFixture,
        gettext: GetTextWrapper
    ) -> None:
        lobby_path = fastapi_module_fixture.app_config["pyknic"]["fastapi"]["lobby"]["main_url_path"]
        lobby_url = f'http://localhost:8000{lobby_path}'

        async with aiohttp.ClientSession() as session:
            fingerprint = await LobbyClient.fingerprint(lobby_url, session)
            assert(isinstance(fingerprint, LobbyFingerprint))

        fingerprint = await LobbyClient.fingerprint(lobby_url)
        assert(isinstance(fingerprint, LobbyFingerprint))

    @AsyncFastAPIFixture.base_config(LobbyApp, __secret_token_yaml__)
    @pyknic_async_test
    async def test_fingerprint_invalid_url(
        self,
        module_event_loop: asyncio.AbstractEventLoop,
        fastapi_module_fixture: AsyncFastAPIFixture,
        gettext: GetTextWrapper
    ) -> None:
        with pytest.raises(BellboyCLIError):
            _ = await LobbyClient.fingerprint('http://localhost:8000/invalid-path')

    @AsyncFastAPIFixture.base_config(LobbyApp, __secret_token_yaml__)
    @pyknic_async_test
    async def test_ping(
        self,
        module_event_loop: asyncio.AbstractEventLoop,
        fastapi_module_fixture: AsyncFastAPIFixture,
        gettext: GetTextWrapper
    ) -> None:
        lobby_path = fastapi_module_fixture.app_config["pyknic"]["fastapi"]["lobby"]["main_url_path"]
        lobby_url = f'http://localhost:8000{lobby_path}'
        client = LobbyClient(lobby_url, await LobbyClient.fingerprint(lobby_url), self.__secret_token__)

        ping_request = LobbyCommandRequest(name='ping', args=NullableModel().model_dump())

        async with aiohttp.ClientSession() as session:
            result = await client.command_request(ping_request, session=session)
            assert(len(result.str_result) > 0)  # type: ignore[union-attr]

        client = LobbyClient(lobby_url, await LobbyClient.fingerprint(lobby_url), 'invalid-token')
        with pytest.raises(BellboyCLIError):
            await client.command_request(ping_request)

    @AsyncFastAPIFixture.base_config(LobbyApp, __secret_token_yaml__)
    @pyknic_async_test
    async def test_invalid_signature_error(
        self,
        module_event_loop: asyncio.AbstractEventLoop,
        fastapi_module_fixture: AsyncFastAPIFixture,
        gettext: GetTextWrapper
    ) -> None:
        lobby_path = fastapi_module_fixture.app_config["pyknic"]["fastapi"]["lobby"]["main_url_path"]
        lobby_url = f'http://localhost:8000{lobby_path}'

        client = LobbyClient(
            lobby_url, LobbyFingerprint.generate_fingerprint(), self.__secret_token__
        )

        ping_request = LobbyCommandRequest(name='ping', args=NullableModel().model_dump())

        with pytest.raises(BellboyCLIError):
            await client.command_request(ping_request)
