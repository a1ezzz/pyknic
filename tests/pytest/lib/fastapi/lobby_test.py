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
        _ = await LobbyCommandHandler.exec(None)


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
            CustomHandler.prepare_command(1)

        cmd = CustomHandler.prepare_command(NullableModel())
        result = await cmd.exec()
        assert(isinstance(result, NullableModel))

#
# class TestLobbyCommandHandler:
#
#     # class ArgLessCommand(LobbyCommandHandler):
#     #
#     #     @classmethod
#     #     def command_name(cls) -> str:
#     #         return 'do'
#     #
#     #     def exec(self) -> LobbyCommandResult:
#     #         return NullableResponseModel()
#     #
#     # class SomeModel(pydantic.BaseModel):
#     #     value: str
#     #
#     # class ArgCommand(LobbyCommandHandler):
#     #
#     #     @classmethod
#     #     def command_name(cls) -> str:
#     #         return 'do-args'
#     #
#     #     @classmethod
#     #     def exec(self) -> LobbyCommandResult:
#     #         return NullableResponseModel()
#
#     def test_exceptions(self) -> None:
#         cmd_handler = TestLobbyCommandHandler.ArgLessCommand
#
#         # check that there are no exceptions
#         cmd = cmd_handler.prepare_command(None, command_mode=LobbyCommandMode.server_command)
#         cmd.exec()
#
#         with pytest.raises(LobbyCommandError):
#             # invalid arguments
#             _ = cmd_handler.prepare_command(NullableResponseModel(), command_mode=LobbyCommandMode.server_command)
#
#         with pytest.raises(LobbyCommandError):
#             # invalid mode
#             _ = cmd_handler.prepare_command(None, command_mode=LobbyCommandMode.bellboy_command)
#
#     def test_invalid_arg_type_exception(self) -> None:
#         cmd_handler = TestLobbyCommandHandler.ArgCommand
#
#         # check that there are no exceptions
#         cmd = cmd_handler.prepare_command(
#             TestLobbyCommandHandler.SomeModel(value="foo"), command_mode=LobbyCommandMode.server_command
#         )
#         cmd.exec()
#
#         with pytest.raises(LobbyCommandError):
#             # invalid arguments
#             _ = cmd_handler.prepare_command(NullableResponseModel(), command_mode=LobbyCommandMode.server_command)
#
#
# class TestLobbyRegistry:
#
#     @pytest.mark.parametrize(
#         'command_handler, command_name, command_args',
#         [
#             [TestLobbyCommandHandler.ArgLessCommand, "do", None],
#             [TestLobbyCommandHandler.ArgCommand, "do-args", {"value": "foo"}]
#         ]
#     )
#     def test_deserialize_command(
#         self,
#         command_handler: typing.Type[LobbyCommandHandler],
#         command_name: str,
#         command_args: typing.Any
#     ) -> None:
#         registry = LobbyRegistry()
#         register_command(registry)(command_handler)
#
#         command = registry.deserialize_command(
#             {"name": command_name, "args": command_args},
#             command_mode=LobbyCommandMode.server_command
#         )
#         assert(isinstance(command, command_handler))
#         command.exec()  # this is ok
#
#     def test_deserialize_exceptions(self) -> None:
#         registry = LobbyRegistry()
#         register_command(registry)(TestLobbyCommandHandler.ArgLessCommand)
#
#         _ = registry.deserialize_command(  # this is ok
#             {"name": "do", "args": None},
#             command_mode=LobbyCommandMode.server_command
#         )
#
#         with pytest.raises(LobbyCommandError):
#             # invalid args
#             _ = registry.deserialize_command(
#                 {"name": "do", "args": {"value": "foo"}},
#                 command_mode=LobbyCommandMode.server_command
#             )
#
#         with pytest.raises(LobbyCommandError):
#             # invalid command mode
#             _ = registry.deserialize_command(
#                 {"name": "do", "args": None},
#                 command_mode=LobbyCommandMode.bellboy_command
#             )
