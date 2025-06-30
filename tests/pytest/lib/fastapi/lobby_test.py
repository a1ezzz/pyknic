# -*- coding: utf-8 -*-

import pytest
import typing

from pyknic.lib.fastapi.lobby import LobbyContextProto, register_context, LobbyCommandDescriptor
from pyknic.lib.fastapi.lobby import SingleLobbyCommandRegistry, LobbyRegistry
from pyknic.lib.registry import APIRegistry, DuplicateAPIIdError


def test_abstract() -> None:
    pytest.raises(TypeError, LobbyContextProto)
    pytest.raises(NotImplementedError, LobbyContextProto.context_name)
    pytest.raises(NotImplementedError, LobbyContextProto.context_type)

    pytest.raises(TypeError, LobbyCommandDescriptor)
    pytest.raises(NotImplementedError, LobbyCommandDescriptor.command_name)
    pytest.raises(NotImplementedError, LobbyCommandDescriptor.exec)


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


class TestLobbyCommandDescriptor:

    def test_defaults(self):
        assert(list(LobbyCommandDescriptor.context_required()) == [])
        assert(list(LobbyCommandDescriptor.kwargs_required()) == [])
        assert(list(LobbyCommandDescriptor.args_required()) == [])

    def test_noargs_model(self):

        class SampleCommand(LobbyCommandDescriptor):
            @classmethod
            def command_name(cls) -> str:
                return 'sample'

            @classmethod
            def exec(cls, *args, **kwargs):
                return None

        model = SampleCommand.pydantic_model()
        assert(model().model_dump() == {'name': 'sample', 'args': None, 'kwargs': None, 'cargs': None})

    def test_args_model(self):

        class SampleCommand(LobbyCommandDescriptor):
            @classmethod
            def command_name(cls) -> str:
                return 'sample'

            @classmethod
            def args_required(cls) -> typing.Generator[typing.Type[typing.Union[int, float, bool, str]], None, None]:
                yield from [int, str]

            @classmethod
            def exec(cls, *args, **kwargs):
                return None

        model = SampleCommand.pydantic_model()
        assert(
            model(args=(10, 'foo')).model_dump() == {
                'name': 'sample', 'args': (10, 'foo'), 'kwargs': None, 'cargs': None
            }
        )

    def test_kwargs_model(self):

        class SampleCommand(LobbyCommandDescriptor):
            @classmethod
            def command_name(cls) -> str:
                return 'sample'

            @classmethod
            def kwargs_required(cls) -> typing.Dict[str, type]:
                return {'foo': int, 'bar': str}

            @classmethod
            def exec(cls, *args, **kwargs):
                return None

        model = SampleCommand.pydantic_model()
        assert(
            model(kwargs={'foo': 10, 'bar': 'xxx'}).model_dump() == {
                'name': 'sample', 'args': None, 'kwargs': {'foo': 10, 'bar': 'xxx'}, 'cargs': None
            }
        )

    def test_cargs_model(self):

        class SampleContext(LobbyContextProto):

            @classmethod
            def context_name(cls) -> str:
                return 'context_var'

            @classmethod
            def context_type(cls) -> type:
                return int

        class SampleCommand(LobbyCommandDescriptor):
            @classmethod
            def command_name(cls) -> str:
                return 'sample'

            @classmethod
            def context_required(cls) -> typing.Generator[LobbyContextProto, None, None]:
                yield from [SampleContext]

            @classmethod
            def exec(cls, *args, **kwargs):
                return None

        model = SampleCommand.pydantic_model()
        assert(
            model(cargs={'context_var': 10}).model_dump() == {
                'name': 'sample', 'args': None, 'kwargs': None, 'cargs': {'context_var': 10}
            }
        )


class TestSingleLobbyCommandRegistry:

    class DoCommand(LobbyCommandDescriptor):
        @classmethod
        def command_name(cls) -> str:
            return 'do'

        @classmethod
        def exec(cls, *args, **kwargs):
            return None

    class ContextCommand(LobbyCommandDescriptor):
        @classmethod
        def context_required(cls) -> typing.Generator[LobbyContextProto, None, None]:
            yield from [TestSingleLobbyCommandRegistry.LobbyContext1]

        @classmethod
        def command_name(cls) -> str:
            return 'do'

        @classmethod
        def exec(cls, *args, **kwargs):
            return None

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

    def test_plain(self):
        context_registry = APIRegistry()
        registry = SingleLobbyCommandRegistry('do', context_registry)
        assert({registry.get(x) for x in registry.ids()} == set())

        registry.register_lobby_command(self.DoCommand)
        assert({registry.get(x) for x in registry.ids()} == {self.DoCommand, })

        class OtherCommand(LobbyCommandDescriptor):
            @classmethod
            def command_name(cls) -> str:
                return 'other'

            @classmethod
            def exec(cls, *args, **kwargs):
                return None

        with pytest.raises(ValueError):
            registry.register_lobby_command(OtherCommand)

    def test_same_command(self):
        context_registry = APIRegistry()
        registry = SingleLobbyCommandRegistry('do', context_registry)
        registry.register_lobby_command(self.DoCommand)

        class SameCommand(LobbyCommandDescriptor):
            @classmethod
            def command_name(cls) -> str:
                return 'do'

            @classmethod
            def exec(cls, *args, **kwargs):
                return None

        with pytest.raises(DuplicateAPIIdError):
            registry.register_lobby_command(SameCommand)

    def test_unknown_context(self):
        context_registry = APIRegistry()
        registry = SingleLobbyCommandRegistry('do', context_registry)

        with pytest.raises(ValueError):
            # no context at the moment
            registry.register_lobby_command(self.ContextCommand)

    def test_context(self):
        context_registry = APIRegistry()
        registry = SingleLobbyCommandRegistry('do', context_registry)
        registry.register_lobby_command(self.DoCommand)

        register_context(context_registry)(self.LobbyContext1)
        registry.register_lobby_command(self.ContextCommand)

    def test_conflicted_context(self):
        context_registry = APIRegistry()
        registry = SingleLobbyCommandRegistry('do', context_registry)
        register_context(context_registry)(self.LobbyContext1)

        class ConflictedContextCommand(LobbyCommandDescriptor):
            @classmethod
            def context_required(cls) -> typing.Generator[LobbyContextProto, None, None]:
                yield from [self.LobbyContext1]

            @classmethod
            def command_name(cls) -> str:
                return 'do'

            @classmethod
            def exec(cls, *args, **kwargs):
                return None

        registry.register_lobby_command(self.ContextCommand)
        with pytest.raises(DuplicateAPIIdError):
            registry.register_lobby_command(ConflictedContextCommand)

    def test_multiple_context_command(self):
        context_registry = APIRegistry()
        registry = SingleLobbyCommandRegistry('do', context_registry)
        registry.register_lobby_command(self.DoCommand)
        register_context(context_registry)(self.LobbyContext1)
        register_context(context_registry)(self.LobbyContext2)

        class MoreContextCommand(LobbyCommandDescriptor):
            @classmethod
            def context_required(cls) -> typing.Generator[LobbyContextProto, None, None]:
                yield from [self.LobbyContext1, self.LobbyContext2]

            @classmethod
            def command_name(cls) -> str:
                return 'do'

            @classmethod
            def exec(cls, *args, **kwargs):
                return None

        registry.register_lobby_command(self.ContextCommand)
        registry.register_lobby_command(MoreContextCommand)

    def test_conflicted_kwargs(self):
        context_registry = APIRegistry()
        registry = SingleLobbyCommandRegistry('do', context_registry)
        register_context(context_registry)(self.LobbyContext1)

        class ConflictedKWArgsCommand(LobbyCommandDescriptor):

            @classmethod
            def kwargs_required(cls) -> typing.Dict[str, type]:
                return {self.LobbyContext1.context_name(): int}

            @classmethod
            def command_name(cls) -> str:
                return 'do'

            @classmethod
            def exec(cls, *args, **kwargs):
                return None

        with pytest.raises(ValueError):
            registry.register_lobby_command(ConflictedKWArgsCommand)


class TestLobbyRegistry:

    def test_plain(self):
        context_registry = APIRegistry()
        registry = LobbyRegistry(context_registry)
        register_context(context_registry)(TestSingleLobbyCommandRegistry.LobbyContext1)

        registry.register_lobby_command(TestSingleLobbyCommandRegistry.DoCommand)
        registry.register_lobby_command(TestSingleLobbyCommandRegistry.ContextCommand)

    def test_deserialize(self):
        context_registry = APIRegistry()
        registry = LobbyRegistry(context_registry)
        register_context(context_registry)(TestSingleLobbyCommandRegistry.LobbyContext1)

        registry.register_lobby_command(TestSingleLobbyCommandRegistry.DoCommand)
        registry.register_lobby_command(TestSingleLobbyCommandRegistry.ContextCommand)

        deserialized_model = registry.deserialize_command(
            {"name": "do", "args": None, "kwargs": None, "cargs": None}
        )
        assert(isinstance(deserialized_model, TestSingleLobbyCommandRegistry.DoCommand.__auto_generated_model__) is True)
        assert(isinstance(deserialized_model, TestSingleLobbyCommandRegistry.ContextCommand.__auto_generated_model__) is False)

        deserialized_model = registry.deserialize_command(
            {"name": "do", "args": None, "kwargs": None, "cargs": {"context_var1": 10}}
        )
        assert(isinstance(deserialized_model, TestSingleLobbyCommandRegistry.DoCommand.__auto_generated_model__) is False)
        assert(isinstance(deserialized_model, TestSingleLobbyCommandRegistry.ContextCommand.__auto_generated_model__) is True)
