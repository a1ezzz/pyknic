# -*- coding: utf-8 -*-

import asyncio
import typing

from pyknic.lib.fastapi.models.base import NullableModel
from pyknic.lib.fastapi.models.lobby import LobbyStrFeedbackResult
from pyknic.lib.bellboy.models import OptionalBellBoyCommandModel, GeneralBellBoyCommandModel, SecretBackendType
from pyknic.lib.integrated_commands.ping import LobbyPingCommand, BellBoyPingCommand
from pyknic.tasks.fastapi.lobby import LobbyApp

from fixtures.asyncio import pyknic_async_test
from fixtures.fastapi import AsyncFastAPIFixture


class TestLobbyPingCommand:

    @pyknic_async_test
    async def test(self, module_event_loop: asyncio.AbstractEventLoop) -> None:
        assert(len(LobbyPingCommand.command_name()) > 0)  # check that there is a name
        assert(LobbyPingCommand.command_model() is NullableModel)

        result = await LobbyPingCommand.exec(args=NullableModel())
        assert(isinstance(result, LobbyStrFeedbackResult))
        assert(len(result.str_result) > 0)  # check that there is a response


class TestBellBoyPingCommand:

    __secret_token__ = 'secret-token'
    __secret_token_yaml__ = f"""
    pyknic:
        fastapi:
            lobby:
                secret_token: {__secret_token__}
    """

    @pyknic_async_test
    async def test_client_side(self, module_event_loop: asyncio.AbstractEventLoop) -> None:
        assert(len(BellBoyPingCommand.command_name()) > 0)  # check that there is a name
        assert(BellBoyPingCommand.command_model() is OptionalBellBoyCommandModel)

        result = await BellBoyPingCommand.exec(args=OptionalBellBoyCommandModel())
        assert(isinstance(result, LobbyStrFeedbackResult))
        assert(len(result.str_result) > 0)  # check that there is a response

    @AsyncFastAPIFixture.base_config(LobbyApp, __secret_token_yaml__)
    @pyknic_async_test
    async def test_server_side(
        self,
        module_event_loop: asyncio.AbstractEventLoop,
        fastapi_module_fixture: AsyncFastAPIFixture,
        lobby_shm_secrets: typing.Callable[[str, str], typing.Coroutine[None, None, None]]
    ) -> None:
        lobby_path = fastapi_module_fixture.app_config["pyknic"]["fastapi"]["lobby"]["main_url_path"]
        lobby_url = f'http://localhost:8000{lobby_path}'

        await lobby_shm_secrets(lobby_url, self.__secret_token__)

        lobby_options = OptionalBellBoyCommandModel(
            server=GeneralBellBoyCommandModel(
                lobby_url=lobby_url,
                secret_backend=SecretBackendType.shm
            )
        )

        result = await BellBoyPingCommand.exec(args=lobby_options)
        assert(isinstance(result, LobbyStrFeedbackResult))
        assert(len(result.str_result) > 0)  # check that there is a response
