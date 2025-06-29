# -*- coding: utf-8 -*-

import pydantic
import pytest
import typing

from pyknic.lib.fastapi.models.lobby import LobbyCommand, LobbyPositionalArgs, LobbyLobbyKeyWordArgs, LobbyKeyWordArgValue


class TestLobbyModels:

    def test_command_name(self):
        class InvalidLobbyCommand(LobbyCommand):
            pass

        with pytest.raises(pydantic.ValidationError):
            _ = InvalidLobbyCommand()

        class SomePrettyCommand(LobbyCommand):
            name: typing.Literal['do'] = pydantic.Field(default='do', frozen=True)

        _ = SomePrettyCommand(name='do')
        with pytest.raises(pydantic.ValidationError):
            _ = SomePrettyCommand(name='do not do')

        cmd_request = SomePrettyCommand()
        assert(cmd_request.name == 'do')
        with pytest.raises(pydantic.ValidationError):
            cmd_request.name = 'do not do'
        assert(cmd_request.name == 'do')  # it is the "do" still

    def test_command_required_args(self):

        class SomePrettyCommandPosArgs(LobbyPositionalArgs):
            values: typing.Tuple[int]

        class SomePrettyCommand(LobbyCommand):
            name: typing.Literal['do'] = pydantic.Field(default='do', frozen=True)
            args: SomePrettyCommandPosArgs

        with pytest.raises(pydantic.ValidationError):
            _ = SomePrettyCommand()  # args is required

        _ = SomePrettyCommand(args=SomePrettyCommandPosArgs(values=(10,)))

        with pytest.raises(pydantic.ValidationError):
            _ = SomePrettyCommand(args=SomePrettyCommandPosArgs(values=(10, 20)))

        with pytest.raises(pydantic.ValidationError):
            _ = SomePrettyCommand(args=SomePrettyCommandPosArgs(values=('some data',)))

    def test_command_required_kwargs(self):

        class SomePrettyCommandKwSingleArg(LobbyKeyWordArgValue):
            name: typing.Literal['parameter1'] = pydantic.Field(default='parameter1', frozen=True)
            value: int

        class SomePrettyCommandKwArgs(LobbyLobbyKeyWordArgs):
            values: typing.Tuple[
                SomePrettyCommandKwSingleArg
            ]

        class SomePrettyCommand(LobbyCommand):
            name: typing.Literal['do'] = pydantic.Field(default='do', frozen=True)
            kwargs: SomePrettyCommandKwArgs

        with pytest.raises(pydantic.ValidationError):
            _ = SomePrettyCommand()  # kwargs is required

        _ = SomePrettyCommand(
            kwargs=SomePrettyCommandKwArgs(
                values=(
                    SomePrettyCommandKwSingleArg(value=1),
                )
            )
        )

        with pytest.raises(pydantic.ValidationError):
            _ = SomePrettyCommand(
                kwargs=SomePrettyCommandKwArgs(
                    values=(SomePrettyCommandKwSingleArg(value='some data'), )
                )
            )

        with pytest.raises(pydantic.ValidationError):
            _ = SomePrettyCommand(
                kwargs=SomePrettyCommandKwArgs(
                    values=(SomePrettyCommandKwSingleArg(value=1), 10)
                )
            )

        with pytest.raises(pydantic.ValidationError):
            _ = SomePrettyCommand(kwargs=SomePrettyCommandKwArgs(values=(10, )))


    def test_command_required_cargs(self):

        class SomePrettyCommandCSingleArg(LobbyKeyWordArgValue):
            name: typing.Literal['parameter1'] = pydantic.Field(default='parameter1', frozen=True)
            value: int

        class SomePrettyCommandCArgs(LobbyLobbyKeyWordArgs):
            values: typing.Tuple[
                SomePrettyCommandCSingleArg
            ]

        class SomePrettyCommand(LobbyCommand):
            name: typing.Literal['do'] = pydantic.Field(default='do', frozen=True)
            cargs: SomePrettyCommandCArgs

        with pytest.raises(pydantic.ValidationError):
            _ = SomePrettyCommand()  # kwargs is required

        _ = SomePrettyCommand(
            cargs=SomePrettyCommandCArgs(
                values=(
                    SomePrettyCommandCSingleArg(value=1),
                )
            )
        )

        with pytest.raises(pydantic.ValidationError):
            _ = SomePrettyCommand(
                cargs=SomePrettyCommandCArgs(
                    values=(SomePrettyCommandCSingleArg(value='some data'), )
                )
            )

        with pytest.raises(pydantic.ValidationError):
            _ = SomePrettyCommand(
                cargs=SomePrettyCommandCArgs(
                    values=(SomePrettyCommandCSingleArg(value=1), 10)
                )
            )

        with pytest.raises(pydantic.ValidationError):
            _ = SomePrettyCommand(kwargs=SomePrettyCommandCArgs(values=(10, )))

    def test_command_shortener(self):

        class SomePrettyCommandPosArgs(LobbyPositionalArgs):
            values: typing.Tuple[int]

        class SomePrettyCommandKwSingleArg(LobbyKeyWordArgValue):
            name: typing.Literal['parameter1'] = pydantic.Field(default='parameter1', frozen=True)
            value: int

        class SomePrettyCommandKwArgs(LobbyLobbyKeyWordArgs):
            values: typing.Tuple[
                SomePrettyCommandKwSingleArg
            ]

        class SomePrettyCommandCSingleArg(LobbyKeyWordArgValue):
            name: typing.Literal['parameter1'] = pydantic.Field(default='parameter1', frozen=True)
            value: int

        class SomePrettyCommandCArgs(LobbyLobbyKeyWordArgs):
            values: typing.Tuple[
                SomePrettyCommandCSingleArg
            ]

        class SomePrettyCommand(LobbyCommand):
            name: typing.Literal['do'] = pydantic.Field(default='do', frozen=True)
            args: SomePrettyCommandPosArgs
            kwargs: SomePrettyCommandKwArgs
            cargs: SomePrettyCommandCArgs

        fully_qualified_cmd = SomePrettyCommand(
            args=SomePrettyCommandPosArgs(values=(10,)),
            kwargs=SomePrettyCommandKwArgs(values=(SomePrettyCommandKwSingleArg(value=20),)),
            cargs=SomePrettyCommandCArgs(values=(SomePrettyCommandCSingleArg(value=30),)),
        )
        _ = fully_qualified_cmd.model_dump()
