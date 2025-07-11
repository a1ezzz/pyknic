
import asyncio
import pytest

import aiohttp

from pyknic.lib.bellboy.client import LobbyClient
from pyknic.lib.bellboy.error import BellboyCLIError
from pyknic.tasks.fastapi.lobby import LobbyApp
from pyknic.lib.fastapi.lobby_fingerprint import LobbyFingerprint
from pyknic.lib.gettext import GetTextWrapper
from pyknic.lib.bellboy.console import BellboyPromptParser

from fixtures.asyncio import pyknic_async_test
from fixtures.fastapi import AsyncFastAPIFixture


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

        client = LobbyClient(lobby_url, self.__secret_token__)
        assert(client.url() == lobby_url)

        async with aiohttp.ClientSession() as session:
            fingerprint = await client.fingerprint(session)
            assert(isinstance(fingerprint, LobbyFingerprint))

            client.set_token('invalid-token')  # token is not checked for fingerprint
            fingerprint = await client.fingerprint(session)
            assert(isinstance(fingerprint, LobbyFingerprint))

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
        client = LobbyClient(lobby_url, self.__secret_token__)

        async with aiohttp.ClientSession() as session:
            fingerprint = await client.fingerprint(session)
            assert(isinstance(fingerprint, LobbyFingerprint))

            result = await client.command_request(fingerprint, session, BellboyPromptParser('ping', tuple()))
            assert(len(result) > 0)

            client.set_token('invalid-token')  # token is not checked for fingerprint
            with pytest.raises(BellboyCLIError):
                await client.command_request(fingerprint, session, BellboyPromptParser('ping', tuple()))

    @AsyncFastAPIFixture.base_config(LobbyApp, __secret_token_yaml__)
    @pyknic_async_test
    async def test_fingerprint_error(
        self,
        module_event_loop: asyncio.AbstractEventLoop,
        fastapi_module_fixture: AsyncFastAPIFixture,
        gettext: GetTextWrapper
    ) -> None:
        client = LobbyClient('http://localhost:8000/invalid-path', self.__secret_token__)

        async with aiohttp.ClientSession() as session:
            with pytest.raises(BellboyCLIError):
                await client.fingerprint(session)

    @AsyncFastAPIFixture.base_config(LobbyApp, __secret_token_yaml__)
    @pyknic_async_test
    async def test_no_token_error(
        self,
        module_event_loop: asyncio.AbstractEventLoop,
        fastapi_module_fixture: AsyncFastAPIFixture,
        gettext: GetTextWrapper
    ) -> None:
        lobby_path = fastapi_module_fixture.app_config["pyknic"]["fastapi"]["lobby"]["main_url_path"]
        lobby_url = f'http://localhost:8000{lobby_path}'
        client = LobbyClient(lobby_url, None)

        async with aiohttp.ClientSession() as session:
            fingerprint = await client.fingerprint(session)
            with pytest.raises(BellboyCLIError):
                await client.command_request(fingerprint, session, BellboyPromptParser('ping', tuple()))

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
        client = LobbyClient(lobby_url, self.__secret_token__)

        async with aiohttp.ClientSession() as session:
            fingerprint = LobbyFingerprint.generate_fingerprint()  # this is a totally new fingerprint
            with pytest.raises(BellboyCLIError):
                await client.command_request(fingerprint, session, BellboyPromptParser('ping', tuple()))
