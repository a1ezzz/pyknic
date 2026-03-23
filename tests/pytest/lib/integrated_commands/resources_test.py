# -*- coding: utf-8 -*-

import asyncio
import typing

from pyknic.lib.integrated_commands.resources import LobbyResourcesCommand, BellBoyResourcesCommand
from pyknic.lib.fastapi.models.base import NullableModel
from pyknic.lib.fastapi.models.lobby import LobbyKeyValueFeedbackResult
from pyknic.lib.bellboy.models import GeneralBellBoyCommandModel, SecretBackendType
from pyknic.tasks.fastapi.lobby import LobbyApp

from fixtures.asyncio import pyknic_async_test
from fixtures.fastapi import AsyncFastAPIFixture


class TestLobbyResourcesCommand:

    @pyknic_async_test
    async def test(self, module_event_loop: asyncio.AbstractEventLoop) -> None:
        assert(len(LobbyResourcesCommand.command_name()) > 0)  # check that there is a name
        assert(LobbyResourcesCommand.command_model() is NullableModel)

        result = await LobbyResourcesCommand.prepare_command(NullableModel()).exec()
        assert(isinstance(result, LobbyKeyValueFeedbackResult))
        assert(len(result.kv_result) > 0)  # check that there is a response


class TestBellBoyResourcesCommand:

    __secret_token__ = 'secret-token'
    __secret_token_yaml__ = f"""
    pyknic:
        fastapi:
            lobby:
                secret_token: {__secret_token__}
    """

    @AsyncFastAPIFixture.base_config(LobbyApp, __secret_token_yaml__)
    @pyknic_async_test
    async def test(
        self,
        module_event_loop: asyncio.AbstractEventLoop,
        fastapi_module_fixture: AsyncFastAPIFixture,
        lobby_shm_secrets: typing.Callable[[str, str], typing.Coroutine[None, None, None]]
    ) -> None:
        lobby_path = fastapi_module_fixture.app_config["pyknic"]["fastapi"]["lobby"]["main_url_path"]
        lobby_url = f'http://localhost:8000{lobby_path}'

        await lobby_shm_secrets(lobby_url, self.__secret_token__)

        lobby_options = GeneralBellBoyCommandModel(
            lobby_url=lobby_url,
            secret_backend=SecretBackendType.shm
        )

        result = await BellBoyResourcesCommand.prepare_command(lobby_options).exec()
        assert(isinstance(result, LobbyKeyValueFeedbackResult))
        assert(len(result.kv_result) > 0)  # check that there is a response
