# -*- coding: utf-8 -*-

import asyncio
import pytest
import typing

from _pytest.monkeypatch import MonkeyPatch

from pyknic.lib.integrated_commands.login import LoginCommand
from pyknic.lib.bellboy.app import BellboyCLIError
from pyknic.lib.bellboy.models import GeneralBellBoyCommandModel, SecretBackendType
from pyknic.lib.fastapi.models.lobby import LobbyStrFeedbackResult
from pyknic.tasks.fastapi.lobby import LobbyApp

from fixtures.asyncio import pyknic_async_test
from fixtures.fastapi import AsyncFastAPIFixture


class TestLoginCommand:

    __secret_token__ = 'secret-token'
    __secret_token_yaml__ = f"""
    pyknic:
        fastapi:
            lobby:
                secret_token: {__secret_token__}
    """

    @classmethod
    def ask_patch(cls, msg: str) -> typing.Callable[[typing.Any], str]:
        def patched_ask(*args: typing.Any, **kwargs: typing.Any) -> str:
            return msg

        return patched_ask

    @AsyncFastAPIFixture.base_config(LobbyApp, __secret_token_yaml__)
    @pyknic_async_test
    async def test(
        self,
        monkeypatch: MonkeyPatch,
        module_event_loop: asyncio.AbstractEventLoop,
        fastapi_module_fixture: AsyncFastAPIFixture,
        lobby_shm_secrets: typing.Callable[[str, str], typing.Coroutine[None, None, None]]
    ) -> None:
        assert(len(LoginCommand.command_name()) > 0)  # check that there is a name
        assert(LoginCommand.command_model() is GeneralBellBoyCommandModel)

        lobby_path = fastapi_module_fixture.app_config["pyknic"]["fastapi"]["lobby"]["main_url_path"]
        lobby_url = f'http://localhost:8000{lobby_path}'

        lobby_options = GeneralBellBoyCommandModel(
            lobby_url=lobby_url,
            secret_backend=SecretBackendType.shm
        )

        monkeypatch.setattr('rich.prompt.Prompt.ask', TestLoginCommand.ask_patch("foo"))
        with pytest.raises(BellboyCLIError):
            # 401 exception
            await LoginCommand.prepare_command(lobby_options).exec()

        monkeypatch.setattr(
            'rich.prompt.Prompt.ask',
            TestLoginCommand.ask_patch(self.__secret_token__)
        )

        result = await LoginCommand.prepare_command(lobby_options).exec()
        assert(isinstance(result, LobbyStrFeedbackResult))
        assert(len(result.str_result) > 0)  # check that there is a response
