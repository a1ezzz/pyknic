# -*- coding: utf-8 -*-

import asyncio
import io
import typing

import aiohttp
import fastapi
import pytest

from pyknic.tasks.fastapi.lobby import LobbyApp
from pyknic.lib.gettext import GetTextWrapper
from pyknic.lib.config import Config
from pyknic.path import root_path

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

    def test_config(self, gettext: GetTextWrapper):
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
    async def test(
        self,
        module_event_loop: asyncio.AbstractEventLoop,
        fastapi_module_fixture: AsyncFastAPIFixture,
        gettext: GetTextWrapper
    ) -> None:
        lobby_path = fastapi_module_fixture.app_config["pyknic"]["fastapi"]["lobby"]["main_url_path"]
        lobby_url = f'http://localhost:8000{lobby_path}'

        session = aiohttp.ClientSession()
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
