# -*- coding: utf-8 -*-
import pydantic
import pytest
import typing

from pyknic.lib.fastapi.lobby import LobbyContextProto, register_context, LobbyCommandDescriptorProto, register_command
from pyknic.lib.fastapi.lobby import SingleLobbyCommandRegistry, LobbyRegistry, LobbyCommandMeta, LobbyCommandError
from pyknic.lib.fastapi.models.lobby import LobbyCommand, LobbyCommandResult
from pyknic.lib.fastapi.models.base import NullableResponseModel
from pyknic.lib.registry import APIRegistry, DuplicateAPIIdError


def test_abstract() -> None:
    pytest.raises(TypeError, LobbyContextProto)
    pytest.raises(NotImplementedError, LobbyContextProto.context_name)
    pytest.raises(NotImplementedError, LobbyContextProto.context_type)

    pytest.raises(TypeError, LobbyCommandDescriptorProto)
    pytest.raises(NotImplementedError, LobbyCommandDescriptorProto.command_name)
    pytest.raises(NotImplementedError, LobbyCommandDescriptorProto.exec, LobbyCommand(name='some_command'))


def test_exception() -> None:
    class A(metaclass=LobbyCommandMeta):
        pass

    with pytest.raises(TypeError):
        A.pydantic_model()


def test_register_context() -> None:
    registry = APIRegistry()
    assert(registry.has('context1') is False)

    @register_context(registry)
    class Context1(LobbyContextProto):

        @classmethod
        def context_name(cls) -> str:
            return "context1"

        @classmethod
        def context_type(cls) -> type:
            return int

    assert(registry.has('context1') is True)

    with pytest.raises(NotImplementedError):
        # no inheritance

        @register_context(registry)
        class Context2:

            @classmethod
            def context_name(cls) -> str:
                return "context1"

            @classmethod
            def context_type(cls) -> type:
                return int


class TestLobbyCommandDescriptorProto:

    def test_defaults(self) -> None:
        assert(list(LobbyCommandDescriptorProto.context_required()) == [])
        assert(list(LobbyCommandDescriptorProto.kwargs_required()) == [])
        assert(list(LobbyCommandDescriptorProto.args_required()) == [])

    def test_noargs_model(self) -> None:

        class SampleCommand(LobbyCommandDescriptorProto):
            @classmethod
            def command_name(cls) -> str:
                return 'sample'

            @classmethod
            def exec(cls, args: LobbyCommand) -> LobbyCommandResult:
                return NullableResponseModel()

        model = SampleCommand.pydantic_model()
        dump_result = model(name='sample').model_dump()
        assert(dump_result == {'name': 'sample', 'args': None, 'kwargs': None, 'cargs': None})

    def test_no_command_model(self) -> None:

        class SampleCommand(LobbyCommandDescriptorProto):
            @classmethod
            def command_name(cls) -> str:
                return 'sample'

        model = SampleCommand.pydantic_model()
        dump_result = model(name='sample').model_dump()
        assert(dump_result == {'name': 'sample', 'args': None, 'kwargs': None, 'cargs': None})

        with pytest.raises(pydantic.ValidationError):
            # a test that no defaults allowed
            model().model_dump()  # type: ignore[call-arg]

        with pytest.raises(pydantic.ValidationError):
            model(name='unknown').model_dump()  # invalid name

    def test_args_model(self) -> None:

        class SampleCommand(LobbyCommandDescriptorProto):
            @classmethod
            def command_name(cls) -> str:
                return 'sample'

            @classmethod
            def args_required(cls) -> typing.Generator[typing.Type[typing.Union[int, float, bool, str]], None, None]:
                yield from [int, str]

            @classmethod
            def exec(cls, args: LobbyCommand) -> LobbyCommandResult:
                return NullableResponseModel()

        model = SampleCommand.pydantic_model()
        dump_result = model(name='sample', args=(10, 'foo')).model_dump()  # type: ignore[arg-type]
        assert(dump_result == {'name': 'sample', 'args': (10, 'foo'), 'kwargs': None, 'cargs': None})

    def test_kwargs_model(self) -> None:

        class SampleCommand(LobbyCommandDescriptorProto):
            @classmethod
            def command_name(cls) -> str:
                return 'sample'

            @classmethod
            def kwargs_required(cls) -> typing.Dict[str, type]:
                return {'foo': int, 'bar': str}

            @classmethod
            def exec(cls, args: LobbyCommand) -> LobbyCommandResult:
                return NullableResponseModel()

        model = SampleCommand.pydantic_model()
        dump_result = model(name='sample', kwargs={'foo': 10, 'bar': 'xxx'}).model_dump()  # type: ignore[arg-type]
        assert(dump_result == {'name': 'sample', 'args': None, 'kwargs': {'foo': 10, 'bar': 'xxx'}, 'cargs': None})

    def test_cargs_model(self) -> None:

        class SampleContext(LobbyContextProto):

            @classmethod
            def context_name(cls) -> str:
                return 'context_var'

            @classmethod
            def context_type(cls) -> type:
                return int

        class SampleCommand(LobbyCommandDescriptorProto):
            @classmethod
            def command_name(cls) -> str:
                return 'sample'

            @classmethod
            def context_required(cls) -> typing.Generator[typing.Type[LobbyContextProto], None, None]:
                yield from [SampleContext]

            @classmethod
            def exec(cls, args: LobbyCommand) -> LobbyCommandResult:
                return NullableResponseModel()

        model = SampleCommand.pydantic_model()
        dump_result = model(name='sample', cargs={'context_var': 10}).model_dump()  # type: ignore[arg-type]
        assert(dump_result == {'name': 'sample', 'args': None, 'kwargs': None, 'cargs': {'context_var': 10}})


class TestSingleLobbyCommandRegistry:

    class DoCommand(LobbyCommandDescriptorProto):
        @classmethod
        def command_name(cls) -> str:
            return 'do'

        @classmethod
        def exec(cls, args: LobbyCommand) -> LobbyCommandResult:
            return NullableResponseModel()

    class ContextCommand(LobbyCommandDescriptorProto):
        @classmethod
        def context_required(cls) -> typing.Generator[typing.Type[LobbyContextProto], None, None]:
            yield from [TestSingleLobbyCommandRegistry.LobbyContext1]

        @classmethod
        def command_name(cls) -> str:
            return 'do'

        @classmethod
        def exec(cls, args: LobbyCommand) -> LobbyCommandResult:
            return NullableResponseModel()

    class MoreContextCommand(LobbyCommandDescriptorProto):
        @classmethod
        def context_required(cls) -> typing.Generator[typing.Type[LobbyContextProto], None, None]:
            yield from [TestSingleLobbyCommandRegistry.LobbyContext1, TestSingleLobbyCommandRegistry.LobbyContext2]

        @classmethod
        def command_name(cls) -> str:
            return 'do'

        @classmethod
        def exec(cls, args: LobbyCommand) -> LobbyCommandResult:
            return NullableResponseModel()

    class LobbyContext1(LobbyContextProto):
        @classmethod
        def context_name(cls) -> str:
            return 'context_var1'

        @classmethod
        def context_type(cls) -> type:
            return int

    class LobbyContext2(LobbyContextProto):
        @classmethod
        def context_name(cls) -> str:
            return 'context_var2'

        @classmethod
        def context_type(cls) -> type:
            return int

    def test_plain(self) -> None:
        context_registry = APIRegistry()
        registry = SingleLobbyCommandRegistry('do', context_registry)
        assert({registry.get(x) for x in registry.ids()} == set())

        registry.register_lobby_command(self.DoCommand)
        assert({registry.get(x) for x in registry.ids()} == {self.DoCommand, })

        class OtherCommand(LobbyCommandDescriptorProto):
            @classmethod
            def command_name(cls) -> str:
                return 'other'

            @classmethod
            def exec(cls, args: LobbyCommand) -> LobbyCommandResult:
                return NullableResponseModel()

        with pytest.raises(ValueError):
            registry.register_lobby_command(OtherCommand)

    def test_same_command(self) -> None:
        context_registry = APIRegistry()
        registry = SingleLobbyCommandRegistry('do', context_registry)
        registry.register_lobby_command(self.DoCommand)

        class SameCommand(LobbyCommandDescriptorProto):
            @classmethod
            def command_name(cls) -> str:
                return 'do'

            @classmethod
            def exec(cls, args: LobbyCommand) -> LobbyCommandResult:
                return NullableResponseModel()

        with pytest.raises(DuplicateAPIIdError):
            registry.register_lobby_command(SameCommand)

    def test_unknown_context(self) -> None:
        context_registry = APIRegistry()
        registry = SingleLobbyCommandRegistry('do', context_registry)

        with pytest.raises(ValueError):
            # no context at the moment
            registry.register_lobby_command(self.ContextCommand)

    def test_context(self) -> None:
        context_registry = APIRegistry()
        registry = SingleLobbyCommandRegistry('do', context_registry)
        registry.register_lobby_command(self.DoCommand)

        register_context(context_registry)(self.LobbyContext1)
        registry.register_lobby_command(self.ContextCommand)

    def test_conflicted_context(self) -> None:
        context_registry = APIRegistry()
        registry = SingleLobbyCommandRegistry('do', context_registry)
        register_context(context_registry)(self.LobbyContext1)

        class ConflictedContextCommand(LobbyCommandDescriptorProto):
            @classmethod
            def context_required(cls) -> typing.Generator[typing.Type[LobbyContextProto], None, None]:
                yield from [self.LobbyContext1]

            @classmethod
            def command_name(cls) -> str:
                return 'do'

            @classmethod
            def exec(cls, args: LobbyCommand) -> LobbyCommandResult:
                return NullableResponseModel()

        registry.register_lobby_command(self.ContextCommand)
        with pytest.raises(DuplicateAPIIdError):
            registry.register_lobby_command(ConflictedContextCommand)

    def test_multiple_context_command(self) -> None:
        context_registry = APIRegistry()
        registry = SingleLobbyCommandRegistry('do', context_registry)
        registry.register_lobby_command(self.DoCommand)
        register_context(context_registry)(self.LobbyContext1)
        register_context(context_registry)(self.LobbyContext2)

        registry.register_lobby_command(self.ContextCommand)
        registry.register_lobby_command(self.MoreContextCommand)

    def test_conflicted_kwargs(self) -> None:
        context_registry = APIRegistry()
        registry = SingleLobbyCommandRegistry('do', context_registry)
        register_context(context_registry)(self.LobbyContext1)

        class ConflictedKWArgsCommand(LobbyCommandDescriptorProto):

            @classmethod
            def kwargs_required(cls) -> typing.Dict[str, type]:
                return {self.LobbyContext1.context_name(): int}

            @classmethod
            def command_name(cls) -> str:
                return 'do'

            @classmethod
            def exec(cls, args: LobbyCommand) -> LobbyCommandResult:
                return NullableResponseModel()

        with pytest.raises(ValueError):
            registry.register_lobby_command(ConflictedKWArgsCommand)


class TestLobbyRegistry:

    def test_plain(self) -> None:
        context_registry = APIRegistry()
        registry = LobbyRegistry(context_registry)
        register_context(context_registry)(TestSingleLobbyCommandRegistry.LobbyContext1)

        registry.register_lobby_command(TestSingleLobbyCommandRegistry.DoCommand)
        registry.register_lobby_command(TestSingleLobbyCommandRegistry.ContextCommand)

    def test_exceptions(self) -> None:
        context_registry = APIRegistry()
        registry = LobbyRegistry(context_registry)

        class NullCommandOrigin(LobbyCommandDescriptorProto):
            @classmethod
            def command_name(cls) -> str:
                return 'do'

            @classmethod
            def pydantic_model(cls) -> typing.Type[LobbyCommand]:
                return LobbyCommand

            @classmethod
            def exec(cls, args: LobbyCommand) -> LobbyCommandResult:
                return NullableResponseModel()

        with pytest.raises(ValueError):
            registry.register_lobby_command(NullCommandOrigin)

        class InvalidCommandModel(LobbyCommand):
            _command_origin = 1  # type: ignore[assignment]

        class InvalidCommandOrigin(LobbyCommandDescriptorProto):
            @classmethod
            def command_name(cls) -> str:
                return 'do'

            @classmethod
            def pydantic_model(cls) -> typing.Type[LobbyCommand]:
                return InvalidCommandModel

            @classmethod
            def exec(cls, args: LobbyCommand) -> LobbyCommandResult:
                return NullableResponseModel()

        with pytest.raises(ValueError):
            registry.register_lobby_command(InvalidCommandOrigin)

    def test_deserialize(self) -> None:
        context_registry = APIRegistry()
        registry = LobbyRegistry(context_registry)
        register_context(context_registry)(TestSingleLobbyCommandRegistry.LobbyContext1)

        with pytest.raises(ValueError):
            # no commands
            _ = registry.deserialize_command(
                {"name": "do", "args": None, "kwargs": None, "cargs": None}
            )

        registry.register_lobby_command(TestSingleLobbyCommandRegistry.DoCommand)
        registry.register_lobby_command(TestSingleLobbyCommandRegistry.ContextCommand)

        with pytest.raises(LobbyCommandError):
            # unknown commands
            _ = registry.deserialize_command(
                {"name": "unknown", "args": None, "kwargs": None, "cargs": None}
            )

        command, model = registry.deserialize_command(
            {"name": "do", "args": None, "kwargs": None, "cargs": None}
        )
        assert(command is TestSingleLobbyCommandRegistry.DoCommand)
        assert(model.args is None)
        assert(model.kwargs is None)
        assert(model.cargs is None)

        command, model = registry.deserialize_command(
            {"name": "do", "args": None, "kwargs": None, "cargs": {"context_var1": 10}}
        )
        assert(command is TestSingleLobbyCommandRegistry.ContextCommand)
        assert(model.args is None)
        assert(model.kwargs is None)
        assert(model.cargs.context_var1 == 10)  # type: ignore[attr-defined]

    def test_list_commands(self) -> None:
        context_registry = APIRegistry()
        registry = LobbyRegistry(context_registry)
        register_context(context_registry)(TestSingleLobbyCommandRegistry.LobbyContext1)
        register_context(context_registry)(TestSingleLobbyCommandRegistry.LobbyContext2)

        assert(list(registry.list_commands(None)) == [])

        class OtherCommand(LobbyCommandDescriptorProto):
            @classmethod
            def command_name(cls) -> str:
                return 'other_command'

            @classmethod
            def exec(cls, command: LobbyCommand) -> LobbyCommandResult:
                return NullableResponseModel()

        registry.register_lobby_command(TestSingleLobbyCommandRegistry.DoCommand)
        registry.register_lobby_command(TestSingleLobbyCommandRegistry.ContextCommand)
        registry.register_lobby_command(TestSingleLobbyCommandRegistry.MoreContextCommand)
        registry.register_lobby_command(OtherCommand)

        assert(set(registry.list_commands(None)) == {
            TestSingleLobbyCommandRegistry.DoCommand,
            TestSingleLobbyCommandRegistry.ContextCommand,
            TestSingleLobbyCommandRegistry.MoreContextCommand,
            OtherCommand
        })

        assert(set(registry.list_commands('do')) == {
            TestSingleLobbyCommandRegistry.DoCommand,
            TestSingleLobbyCommandRegistry.ContextCommand,
            TestSingleLobbyCommandRegistry.MoreContextCommand
        })

        assert(set(registry.list_commands('other_command')) == {OtherCommand, })

        assert(list(registry.list_commands('other_command', 'context_var1')) == [])

        assert(set(registry.list_commands(None, 'context_var1')) == {
            TestSingleLobbyCommandRegistry.ContextCommand,
            TestSingleLobbyCommandRegistry.MoreContextCommand
        })

        assert(set(registry.list_commands('do', 'context_var1')) == {
            TestSingleLobbyCommandRegistry.ContextCommand,
            TestSingleLobbyCommandRegistry.MoreContextCommand
        })

        assert(set(registry.list_commands(None, 'context_var1', 'context_var2')) == {
            TestSingleLobbyCommandRegistry.MoreContextCommand
        })

        assert(set(registry.list_commands('do', 'context_var1', 'context_var2')) == {
            TestSingleLobbyCommandRegistry.MoreContextCommand
        })

    def test_list_contexts(self) -> None:
        context_registry = APIRegistry()
        registry = LobbyRegistry(context_registry)

        assert(list(registry.list_contexts()) == [])

        register_context(context_registry)(TestSingleLobbyCommandRegistry.LobbyContext1)
        assert(list(registry.list_contexts()) == ['context_var1'])

        register_context(context_registry)(TestSingleLobbyCommandRegistry.LobbyContext2)
        result = list(registry.list_contexts())
        result.sort()
        assert(list(registry.list_contexts()) == ['context_var1', 'context_var2'])


def test_register_command() -> None:
    context_registry = APIRegistry()
    registry = LobbyRegistry(context_registry)

    register_command(registry=registry)(TestSingleLobbyCommandRegistry.DoCommand)

    command, model = registry.deserialize_command(
        {"name": "do", "args": None, "kwargs": None, "cargs": None}
    )
    assert (command is TestSingleLobbyCommandRegistry.DoCommand)
