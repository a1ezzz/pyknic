# -*- coding: utf-8 -*-

import asyncio
import typing

from pyknic.lib.integrated_commands.resources import LobbyResourcesCommand, BellBoyResourcesCommand
from pyknic.lib.fastapi.models.base import NullableModel
from pyknic.lib.fastapi.models.lobby import LobbyKeyValueFeedbackResult
from pyknic.lib.bellboy.models import RequiredMainBellBoyCommandModel, SecretBackendType, MainBellBoyCommandModel
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
    async def test(
        self,
        module_event_loop: asyncio.AbstractEventLoop,
        fastapi_module_fixture: AsyncFastAPIFixture,
        lobby_shm_secrets: typing.Callable[[str], typing.Coroutine[None, None, None]]
    ) -> None:
        lobby_path = fastapi_module_fixture.app_config["pyknic"]["fastapi"]["lobby"]["main_url_path"]
        lobby_url = f'http://localhost:8000{lobby_path}'

        await lobby_shm_secrets(lobby_url)

        lobby_options = RequiredMainBellBoyCommandModel(
            server=MainBellBoyCommandModel(
                lobby_url=lobby_url,
                secret_backend=SecretBackendType.shm
            )
        )

        result = await BellBoyResourcesCommand.prepare_command(lobby_options).exec()
        assert(isinstance(result, LobbyKeyValueFeedbackResult))
        assert(len(result.kv_result) > 0)  # check that there is a response
