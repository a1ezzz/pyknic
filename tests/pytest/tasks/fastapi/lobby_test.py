# -*- coding: utf-8 -*-

import asyncio
import io

import aiohttp
import fastapi
import json
import pytest

from pyknic.tasks.fastapi.lobby import LobbyApp
from pyknic.lib.gettext import GetTextWrapper
from pyknic.lib.config import Config
from pyknic.path import root_path
from pyknic.lib.fastapi.headers import FastAPIHeaders
from pyknic.lib.fastapi.models.lobby import LobbyStrFeedbackResult, LobbyServerFingerprint
from pyknic.lib.fastapi.lobby_fingerprint import LobbyFingerprint

from fixtures.asyncio import pyknic_async_test
from fixtures.fastapi import AsyncFastAPIFixture


class TestLobbyApp:

    __secret_token__ = 'secret-token'
    __invalid_secret_token__ = 'token'
    __secret_token_yaml__ = f"""
    pyknic:
        fastapi:
            lobby:
                secret_token: {__secret_token__}
    """

    def test_config(self, gettext: GetTextWrapper) -> None:
        fastapi_server = fastapi.FastAPI()

        with open(root_path / 'tasks/fastapi/config.yaml') as f:
            default_config = Config(file_obj=f)
        self.gettext = GetTextWrapper(root_path / 'locales')

        with pytest.raises(RuntimeError):
            # secret token is required
            LobbyApp.create_app(fastapi_server, default_config, gettext)

        config = Config()
        config.merge_config(default_config)
        config.merge_config(Config(file_obj=io.StringIO(self.__secret_token_yaml__)))

    @AsyncFastAPIFixture.base_config(LobbyApp, __secret_token_yaml__)
    @pyknic_async_test
    async def test_fingerprint(
        self,
        module_event_loop: asyncio.AbstractEventLoop,
        fastapi_module_fixture: AsyncFastAPIFixture,
        gettext: GetTextWrapper
    ) -> None:
        lobby_path = fastapi_module_fixture.app_config["pyknic"]["fastapi"]["lobby"]["fingerprint_url_path"]
        lobby_url = f'http://localhost:8000{lobby_path}'

        session = aiohttp.ClientSession()
        async with session.get(lobby_url) as response:
            assert(response.status == 200)
            fingerprint = LobbyServerFingerprint.model_validate(await response.json())
            assert(len(fingerprint.fingerprint) > 0)

    @AsyncFastAPIFixture.base_config(LobbyApp, __secret_token_yaml__)
    @pyknic_async_test
    async def test_contexts(
        self,
        module_event_loop: asyncio.AbstractEventLoop,
        fastapi_module_fixture: AsyncFastAPIFixture,
        gettext: GetTextWrapper
    ) -> None:
        lobby_path = fastapi_module_fixture.app_config["pyknic"]["fastapi"]["lobby"]["contexts_url_path"]
        lobby_url = f'http://localhost:8000{lobby_path}'
        headers = {'Authorization': f'Bearer {self.__secret_token__}'}

        session = aiohttp.ClientSession()

        async with session.get(lobby_url, headers=headers) as response:
            assert(response.status == 200)
            assert(await response.json() == [])

        # TODO: try to apply some contexts and check it (LobbyApp may be accessed with
        #   fastapi_module_fixture.configured_with.<...>)
        #   Now it is require to cleanup default contexts
        # async with session.get(lobby_url, headers=headers) as response:
        #     assert(response.status == 200)
        #     assert(await response.json() == ['context1'])

    @AsyncFastAPIFixture.base_config(LobbyApp, __secret_token_yaml__)
    @pyknic_async_test
    async def test(
        self,
        module_event_loop: asyncio.AbstractEventLoop,
        fastapi_module_fixture: AsyncFastAPIFixture,
        gettext: GetTextWrapper
    ) -> None:
        lobby_path = fastapi_module_fixture.app_config["pyknic"]["fastapi"]["lobby"]["main_url_path"]
        fingerprint_path = fastapi_module_fixture.app_config["pyknic"]["fastapi"]["lobby"]["fingerprint_url_path"]
        lobby_url = f'http://localhost:8000{lobby_path}'

        session = aiohttp.ClientSession()
        async with session.get(f'http://localhost:8000{fingerprint_path}') as response:
            fingerprint_model = LobbyServerFingerprint.model_validate(await response.json())
            fingerprint = LobbyFingerprint.deserialize(fingerprint_model.fingerprint.encode('ascii'))

        async with session.post(lobby_url) as response:
            assert(response.status == 403)

        headers = {'Authorization': f'Bearer {self.__invalid_secret_token__}'}
        async with session.post(lobby_url, headers=headers) as response:
            assert(response.status == 401)

        headers = {'Authorization': f'Bearer {self.__secret_token__}'}

        async with session.post(lobby_url, headers=headers) as response:
            assert(response.status == 400)

        async with session.post(lobby_url, headers=headers, data='{}') as response:
            assert(response.status == 400)

        async with session.post(lobby_url, headers=headers, data='{"name": "ping"}') as response:
            assert(response.status == 200)

            fingerprint_signing = response.headers[FastAPIHeaders.fingerprint.value]

            response_data = await response.content.read()
            feedback = LobbyStrFeedbackResult.model_validate(json.loads(response_data))
            assert(len(feedback.result) > 0)
            assert(fingerprint.sign(response_data, encode_base64=True).decode('ascii') == fingerprint_signing)
