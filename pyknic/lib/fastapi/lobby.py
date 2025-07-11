# -*- coding: utf-8 -*-
# pyknic/lib/fastapi/lobby.py
#
# Copyright (C) 2025 the pyknic authors and contributors
# <see AUTHORS file>
#
# This file is part of pyknic.
#
# pyknic is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# pyknic is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with pyknic.  If not, see <http://www.gnu.org/licenses/>.

import itertools
import re
import typing

from abc import ABCMeta, abstractmethod

import pydantic

from pyknic.lib.registry import APIRegistry, APIRegistryProto, register_api, hash_id_by_tokens
from pyknic.lib.fastapi.models.lobby import LobbyCommandResult, LobbyCommand
from pyknic.lib.verify import verify_value


__default_lobby_context_registry__ = APIRegistry()


class LobbyCommandError(Exception):
    """This exception is raised for command execution errors."""
    pass


class LobbyContextProto(metaclass=ABCMeta):
    """ Prototype of a context definition
    """

    @classmethod
    @abstractmethod
    def context_name(cls) -> str:
        """Name of a context. Should be unique."""
        raise NotImplementedError('This method is abstract')

    @classmethod
    @abstractmethod
    def context_type(cls) -> type:
        """Type of context (type of argument)"""
        raise NotImplementedError('This method is abstract')


def register_context(registry: APIRegistryProto | None = None,) -> typing.Callable[..., typing.Callable[..., type]]:
    """Decorate a function, that will register context with the specified registry

    :param registry: Registry to register context with. If not defined then the default one is used
    (__default_lobby_context_registry__)
    """

    if registry is None:
        registry = __default_lobby_context_registry__

    def decorator_fn(decorated_cls: type) -> typing.Callable[..., type]:
        if not issubclass(decorated_cls, LobbyContextProto):
            raise NotImplementedError(
                f'The "{decorated_cls.__name__}" class must derived from the "LobbyContextProto" base class'
            )
        return register_api(registry, decorated_cls.context_name())(decorated_cls)

    return decorator_fn


class LobbyCommandMeta(ABCMeta):
    """ This metaclass helps to generate pydantic model for a lobby command."""

    def __init__(cls, name: str, bases: typing.Tuple[type], namespace: typing.Dict[str, typing.Any]):
        """ Generate new class with this metaclass

        :param name: same as 'name' in :meth:`.ABCMeta.__init__` method
        :param bases: same as 'bases' in :meth:`.ABCMeta.__init__` method
        :param namespace: same as 'namespace' in :meth:`.ABCMeta.__init__` method
        """
        ABCMeta.__init__(cls, name, bases, namespace)
        cls.__generated_model: typing.Type[LobbyCommand] | None = None

    def __model_generator(cls) -> typing.Type[LobbyCommand]:
        """Generate a pydantic model for this class
        """
        if not issubclass(cls, LobbyCommandDescriptorProto):
            raise TypeError('Invalid base class')

        command_name = cls.command_name()

        command_args = tuple(cls.args_required())
        command_args_type = typing.Tuple[*command_args] if command_args else (typing.Tuple[()] | None)
        command_args_field = pydantic.Field() if command_args else pydantic.Field(default=None, frozen=True)

        command_kwargs = cls.kwargs_required()
        command_kwargs_gen_model = pydantic.create_model(  # type: ignore[call-overload]
            f'{command_name}CommandKWArgs', **command_kwargs
        )
        command_kwargs_type = command_kwargs_gen_model if command_kwargs else None
        command_kwargs_field = pydantic.Field() if command_kwargs else pydantic.Field(default=None, frozen=True)

        command_cargs = tuple(cls.context_required())
        command_cargs_dict = {x.context_name(): x.context_type() for x in command_cargs}
        command_cargs_gen_model = pydantic.create_model(  # type: ignore[call-overload]
            f'{command_name}CommandCArgs', **command_cargs_dict
        )
        command_cargs_type = command_cargs_gen_model if command_cargs else None
        command_cargs_field = pydantic.Field() if command_cargs else pydantic.Field(default=None, frozen=True)

        class CommandModel(LobbyCommand):
            model_config = pydantic.ConfigDict(extra='forbid')

            name: typing.Literal[command_name] = pydantic.Field(  # type: ignore[valid-type]
                frozen=True, validate_default=True
            )
            args: command_args_type = command_args_field  # type: ignore[valid-type]
            kwargs: command_kwargs_type = command_kwargs_field  # type: ignore[valid-type]
            cargs: command_cargs_type = command_cargs_field  # type: ignore[valid-type]

            _command_origin = cls
        return CommandModel

    def pydantic_model(cls) -> typing.Type[LobbyCommand]:
        """Return generated pydantic model."""
        if cls.__generated_model is None:
            cls.__generated_model = cls.__model_generator()
        return cls.__generated_model


class LobbyCommandDescriptorProto(metaclass=LobbyCommandMeta):
    """Prototype for a lobby command implementation."""

    @classmethod
    @abstractmethod
    def command_name(cls) -> str:
        """Return name of the command this class implements."""
        raise NotImplementedError('This method is abstract')

    @classmethod
    def context_required(cls) -> typing.Generator[typing.Type[LobbyContextProto], None, None]:
        """Return contexts that this command requires."""
        yield from []

    @classmethod
    def args_required(cls) -> typing.Generator[typing.Type[typing.Union[int, float, bool, str]], None, None]:
        """Return types of positional arguments that this command requires."""
        yield from []

    @classmethod
    def kwargs_required(cls) -> typing.Dict[str, type]:
        """Return types of key word arguments that this command requires."""
        return dict()

    @classmethod
    @abstractmethod
    def exec(cls, args: LobbyCommand) -> LobbyCommandResult:
        """Execute this command with the given arguments.

        :param args: arguments to use
        """
        raise NotImplementedError('This method is abstract')


class SingleLobbyCommandRegistry(APIRegistry):
    """This registry holds commands variation for the same command name (low-level lobby registry)
    """

    __command_name_re__ = re.compile(r'^[a-zA-Z0-9_]+$')

    @verify_value(command_name=lambda x: SingleLobbyCommandRegistry.__command_name_re__.match(x) is not None)
    def __init__(self, command_name: str, context_registry: APIRegistryProto | None = None) -> None:
        """Create a new registry.

        :param command_name: command name this registry holds (this commands with the same name will be used)
        """
        APIRegistry.__init__(self)
        self.__command_name = command_name
        self.__context_registry = \
            context_registry if context_registry is not None else __default_lobby_context_registry__

    def register_lobby_command(self, command: typing.Type[LobbyCommandDescriptorProto]) -> None:
        """Remember the given command.

        :param command: command to register
        """
        if command.command_name() != self.__command_name:
            raise ValueError('Command name mismatch')

        context_names = [x.context_name() for x in command.context_required()]
        for name in context_names:
            if not self.__context_registry.has(name):
                raise ValueError(f'Unknown context "{name}"')

        kwargs_keys = command.kwargs_required().keys()
        for key_name in kwargs_keys:
            if self.__context_registry.has(key_name):
                raise ValueError(f'The "{key_name}" key intersects with known context')

        api_id = hash_id_by_tokens(*context_names, pre_sort=True) if context_names else ''  # empty string as a key for
        # a non-context command
        self.register(api_id, command)


class LobbyRegistry(APIRegistry):
    """High-level registry that hold every given commands and wraps all the routine."""

    def __init__(self, context_registry: APIRegistryProto | None = None) -> None:
        APIRegistry.__init__(self)
        self.__context_registry = context_registry if context_registry else __default_lobby_context_registry__
        self.__command_models: typing.Set[typing.Type[LobbyCommand]] = set()

    def register_lobby_command(self, command: typing.Type[LobbyCommandDescriptorProto]) -> None:
        """ Register the specified command.

        :param command: command to register
        """

        command_name = command.command_name()
        if self.has(command_name):
            single_command_registry = self.get(command_name)
        else:
            single_command_registry = SingleLobbyCommandRegistry(command_name, self.__context_registry)
            self.register(command_name, single_command_registry)

        command_model = command.pydantic_model()
        command_origin = command_model._command_origin

        assert(isinstance(command_origin, pydantic.fields.ModelPrivateAttr) is True)

        origin_default = command_origin.get_default()  # type: ignore[union-attr]

        if origin_default is None:
            raise ValueError('Command origin was not set')

        if not isinstance(origin_default, type) or not issubclass(origin_default, LobbyCommandDescriptorProto):
            raise ValueError('Invalid command origin type')

        single_command_registry.register_lobby_command(command)
        self.__command_models.add(command_model)

    def list_contexts(self) -> typing.Generator[str, None, None]:
        """Iterate over available contexts."""
        yield from self.__context_registry.ids()  # type: ignore[misc]

    def list_commands(
        self, command_name: str | None, *contexts: str
    ) -> typing.Generator[typing.Type[LobbyCommandDescriptorProto], None, None]:
        """Return available commands.

        :param command_name: if specified (ie is not None) then only commands with given name will be returned
        :param contexts: filter available commands and return only those that has specified context names
        """

        if command_name is None:
            registries_subset = {x for _, x in self.__iter__()}
        else:
            registries_subset = {self.get(command_name), }

        commands = (x for _, x in itertools.chain.from_iterable(registries_subset))
        cns = set(contexts)

        yield from filter(
            lambda x: not len(cns.difference(
                {y.context_name() for y in x.context_required()}
            )),
            commands
        )

    def deserialize_command(
        self, json_data: dict[str, typing.Any]
    ) -> typing.Tuple[typing.Type[LobbyCommandDescriptorProto], LobbyCommand]:
        """ Convert pre-parsed JSON to a command and arguments

        :param json_data: JSON data to convert
        """

        if not self.__command_models:
            raise ValueError('No commands registered')

        type_decl = typing.Union[*self.__command_models]  # type: ignore[valid-type, name-defined]
        try:
            model_data: LobbyCommand = pydantic.TypeAdapter(type_decl).validate_python(json_data, strict=True)
            return model_data._command_origin, model_data  # type: ignore[return-value]
        except pydantic.ValidationError:
            raise LobbyCommandError('Invalid JSON data or unknown command')


__default_lobby_commands_registry__ = LobbyRegistry()


def register_command(registry: LobbyRegistry | None = None,) -> typing.Callable[..., typing.Callable[..., type]]:
    """This decorator help to register commands with the given registry."""

    if registry is None:
        registry = __default_lobby_commands_registry__

    def decorator_fn(decorated_cls: type) -> typing.Callable[..., type]:
        registry.register_lobby_command(decorated_cls)
        return decorated_cls

    return decorator_fn
