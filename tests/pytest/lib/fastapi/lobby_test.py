# -*- coding: utf-8 -*-

import asyncio

import pydantic
import pytest
import typing

from pyknic.lib.fastapi.lobby import LobbyCommandError, LobbyCommandHandler
from pyknic.lib.fastapi.models.lobby import LobbyCommandResult
from pyknic.lib.fastapi.models.base import NullableModel

from fixtures.asyncio import pyknic_async_test


def test_exceptions() -> None:
    assert(issubclass(LobbyCommandError, Exception))


@pyknic_async_test
async def test_abstract(module_event_loop: asyncio.AbstractEventLoop) -> None:
    pytest.raises(TypeError, LobbyCommandHandler)
    pytest.raises(NotImplementedError, LobbyCommandHandler.command_name)
    pytest.raises(NotImplementedError, LobbyCommandHandler.command_model)

    with pytest.raises(NotImplementedError):
        _ = await LobbyCommandHandler.exec(None)  # type: ignore[arg-type]


class TestLobbyCommandHandler:

    @pyknic_async_test
    async def test(self, module_event_loop: asyncio.AbstractEventLoop) -> None:

        class CustomHandler(LobbyCommandHandler):

            @classmethod
            def command_name(cls) -> str:
                return 'cmd'

            @classmethod
            def command_model(cls) -> typing.Type[pydantic.BaseModel]:
                return NullableModel

            async def exec(self) -> LobbyCommandResult:
                return NullableModel()

        with pytest.raises(TypeError):
            CustomHandler.prepare_command(1)  # type: ignore[arg-type]

        cmd = CustomHandler.prepare_command(NullableModel())
        result = await cmd.exec()
        assert(isinstance(result, NullableModel))
