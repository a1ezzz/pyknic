# -*- coding: utf-8 -*-

import asyncio
import typing

from pyknic.lib.fastapi.models.base import NullableModel
from pyknic.lib.fastapi.models.lobby import LobbyStrFeedbackResult
from pyknic.lib.bellboy.models import OptionalMainBellBoyCommandModel, SecretBackendType, MainBellBoyCommandModel
from pyknic.lib.integrated_commands.ping import LobbyPingCommand, BellBoyPingCommand
from pyknic.tasks.fastapi.lobby import LobbyApp

from fixtures.asyncio import pyknic_async_test
from fixtures.fastapi import AsyncFastAPIFixture


class TestLobbyPingCommand:

    @pyknic_async_test
    async def test(self, module_event_loop: asyncio.AbstractEventLoop) -> None:
        assert(len(LobbyPingCommand.command_name()) > 0)  # check that there is a name
        assert(LobbyPingCommand.command_model() is NullableModel)

        result = await LobbyPingCommand.prepare_command(NullableModel()).exec()
        assert(isinstance(result, LobbyStrFeedbackResult))
        assert(len(result.str_result) > 0)  # check that there is a response


class TestBellBoyPingCommand:

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

    @pyknic_async_test
    async def test_client_side(self, module_event_loop: asyncio.AbstractEventLoop) -> None:
        assert(len(BellBoyPingCommand.command_name()) > 0)  # check that there is a name
        assert(BellBoyPingCommand.command_model() is OptionalMainBellBoyCommandModel)

        result = await BellBoyPingCommand.prepare_command(OptionalMainBellBoyCommandModel()).exec()
        assert(isinstance(result, LobbyStrFeedbackResult))
        assert(len(result.str_result) > 0)  # check that there is a response

    @AsyncFastAPIFixture.base_config(LobbyApp, __lobby_yaml__)
    @pyknic_async_test
    async def test_server_side(
        self,
        module_event_loop: asyncio.AbstractEventLoop,
        fastapi_module_fixture: AsyncFastAPIFixture,
        lobby_shm_secrets: typing.Callable[[str], typing.Coroutine[None, None, None]]
    ) -> None:
        lobby_path = fastapi_module_fixture.app_config["pyknic"]["fastapi"]["lobby"]["main_url_path"]
        lobby_url = f'http://localhost:8000{lobby_path}'

        await lobby_shm_secrets(lobby_url)

        lobby_options = OptionalMainBellBoyCommandModel(
            server=MainBellBoyCommandModel(
                lobby_url=lobby_url,
                secret_backend=SecretBackendType.shm
            )
        )

        result = await BellBoyPingCommand.prepare_command(lobby_options).exec()
        assert(isinstance(result, LobbyStrFeedbackResult))
        assert(len(result.str_result) > 0)  # check that there is a response
