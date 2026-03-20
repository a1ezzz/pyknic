# -*- coding: utf-8 -*-
# pyknic/lib/fastapi/lobby.py
#
# Copyright (C) 2025-2026 the pyknic authors and contributors
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

import typing

from abc import ABCMeta, abstractmethod

import pydantic

from pyknic.lib.registry import APIRegistry, register_api
from pyknic.lib.fastapi.models.lobby import LobbyCommandResult


class LobbyCommandError(Exception):
    """This exception is raised for command execution errors."""
    pass


class LobbyCommandHandler(metaclass=ABCMeta):
    """Prototype for a lobby command implementation."""

    def __init__(self, args: pydantic.BaseModel):
        if not isinstance(args, self.command_model()):
            raise TypeError(
                f'Invalid argument type for the "{self.command_name()}" command. '
                f'The "{self.command_model().__class__}" was expected, but got {args.__class__}'
            )

        self._args = args

    @classmethod
    @abstractmethod
    def command_name(cls) -> str:
        """Return unique name of this command."""
        raise NotImplementedError('This method is abstract')

    @classmethod
    @abstractmethod
    def command_model(cls) -> typing.Type[pydantic.BaseModel]:
        """Return a model that represents command's arguments.
        """
        raise NotImplementedError('This method is abstract')

    @classmethod
    def prepare_command(cls, args: pydantic.BaseModel) -> 'LobbyCommandHandler':
        """Return instance of this object that is able to call the :meth:`.LobbyCommandHandler.exec` method.

        :param args: command arguments
        """
        return cls(args)

    @abstractmethod
    async def exec(self) -> LobbyCommandResult:
        """ Execute the command and return its result.
        """
        raise NotImplementedError('This method is abstract')


__default_lobby_commands_registry__ = APIRegistry()  # default registry for all commands


def register_lobby_command(
    registry: APIRegistry | None = None,
) -> typing.Callable[..., typing.Any]:
    """This decorator help to register commands with the given registry."""

    if registry is None:
        registry = __default_lobby_commands_registry__

    return register_api(
        registry=registry,
        api_id=lambda x: x.command_name(),
        callable_api_id=True
    )
