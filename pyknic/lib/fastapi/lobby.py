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

# TODO: document the code
# TODO: write tests for the code

import re
import typing

from abc import ABCMeta, abstractmethod

import pydantic

from pyknic.lib.registry import APIRegistry, APIRegistryProto, register_api, hash_id_by_tokens
from pyknic.lib.fastapi.models.lobby import LobbyCommandResult, LobbyCommand, LobbyKeyWordArgs, LobbyContextArg
from pyknic.lib.verify import verify_value


__default_lobby_context_registry__ = APIRegistry()


class LobbyContextProto(metaclass=ABCMeta):

    @classmethod
    @abstractmethod
    def context_name(cls) -> str:
        raise NotImplementedError('This method is abstract')

    @classmethod
    @abstractmethod
    def context_type(cls) -> type:
        raise NotImplementedError('This method is abstract')


def register_context(
    registry: APIRegistryProto | None = None,
) -> typing.Callable[..., typing.Callable[..., type]]:

    if registry is None:
        registry = __default_lobby_context_registry__

    def decorator_fn(decorated_cls: type) -> typing.Callable[..., type]:
        if not issubclass(decorated_cls, LobbyContextProto):
            raise NotImplementedError(
                f'The "{decorated_cls.__name__}" class must derived from the "LobbyContextProto" base class'
            )
        return register_api(registry, decorated_cls.context_name())(decorated_cls)

    return decorator_fn


class LobbyCommandDescriptor(metaclass=ABCMeta):

    __auto_generated_model__ = None

    @classmethod
    @abstractmethod
    def command_name(cls) -> str:
        raise NotImplementedError('This method is abstract')

    @classmethod
    def context_required(cls) -> typing.Generator[LobbyContextProto, None, None]:
        yield from []

    @classmethod
    def args_required(cls) -> typing.Generator[typing.Type[typing.Union[int, float, bool, str]], None, None]:
        yield from []

    @classmethod
    def kwargs_required(cls) -> typing.Dict[str, type]:
        return dict()

    @classmethod
    @abstractmethod
    def exec(cls, *args, **kwargs) -> LobbyCommandResult:
        raise NotImplementedError('This method is abstract')

    @classmethod
    def pydantic_model(cls):
        if cls.__auto_generated_model__ is None:  # TODO: make it with metaclass
            command_name = cls.command_name()

            command_args = tuple(cls.args_required())
            command_args_type = typing.Tuple[*command_args] if command_args else (typing.Tuple[*command_args] | None)
            command_args_field = pydantic.Field() if command_args else pydantic.Field(default=None, frozen=True)

            command_kwargs = cls.kwargs_required()
            command_kwargs_gen_model = pydantic.create_model(f'{command_name}CommandKWArgs', **command_kwargs)
            command_kwargs_type = command_kwargs_gen_model if command_kwargs else typing.Optional[LobbyKeyWordArgs]
            command_kwargs_field = pydantic.Field() if command_kwargs else pydantic.Field(default=None, frozen=True)

            command_cargs = tuple(cls.context_required())
            command_cargs_dict = {x.context_name(): x.context_type() for x in command_cargs}
            command_cargs_gen_model = pydantic.create_model(f'{command_name}CommandCArgs', **command_cargs_dict)
            command_cargs_type = command_cargs_gen_model if command_cargs else typing.Optional[LobbyContextArg]
            command_cargs_field = pydantic.Field() if command_cargs else pydantic.Field(default=None, frozen=True)

            class CommandModel(LobbyCommand):
                name: typing.Literal[command_name] = pydantic.Field(default=command_name, frozen=True)
                args: command_args_type = command_args_field
                kwargs: command_kwargs_type = command_kwargs_field
                cargs: command_cargs_type = command_cargs_field

            cls.__auto_generated_model__ = CommandModel

        return cls.__auto_generated_model__


class SingleLobbyCommandRegistry(APIRegistry):
    """ This registry holds commands variation for the same command name
    """

    __command_name_re__ = re.compile(r'^[a-zA-Z0-9_]+$')

    @verify_value(command_name=lambda x: SingleLobbyCommandRegistry.__command_name_re__.match(x) is not None)
    def __init__(self, command_name: str, context_registry: APIRegistryProto | None = None) -> None:
        APIRegistry.__init__(self)
        self.__command_name = command_name
        self.__context_registry = \
            context_registry if context_registry is not None else __default_lobby_context_registry__

    def register_lobby_command(self, command: LobbyCommandDescriptor):
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

    def __init__(self, context_registry: APIRegistryProto | None = None) -> None:
        APIRegistry.__init__(self)
        self.__context_registry = context_registry
        self.__command_models = set()

    def register_lobby_command(self, command: LobbyCommandDescriptor):
        command_name = command.command_name()
        if self.has(command_name):
            single_command_registry = self.get(command_name)
            single_command_registry.register_lobby_command(command)
        else:
            single_command_registry = SingleLobbyCommandRegistry(command_name, self.__context_registry)
            single_command_registry.register_lobby_command(command)
            self.register(command_name, single_command_registry)
        self.__command_models.add(command.pydantic_model())

    def list_entries(self, command: str | None, **contexts):
        # TODO: return commands and contexts that are available for specified contexts
        pass

    def deserialize_command(self, json_data):
        # TODO: return model so as related command handler
        type_decl = typing.Union[LobbyKeyWordArgs, *self.__command_models]
        model_data = pydantic.TypeAdapter(type_decl).validate_python(json_data)
        return model_data


__default_lobby_commands_registry__ = LobbyRegistry()
