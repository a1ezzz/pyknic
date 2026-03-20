# -*- coding: utf-8 -*-
# pyknic/lib/integrated_commands/ping.py
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

import pydantic

from pyknic.lib.bellboy.app import BellBoyCommandHandler, register_bellboy_command, LobbyClient
from pyknic.lib.bellboy.models import OptionalBellBoyCommandModel
from pyknic.lib.fastapi.lobby import LobbyCommandHandler, register_lobby_command
from pyknic.lib.fastapi.models.base import NullableModel
from pyknic.lib.fastapi.models.lobby import LobbyCommandResult, LobbyStrFeedbackResult, LobbyCommandRequest

from pyknic.version import __version__


@register_lobby_command()
class LobbyPingCommand(LobbyCommandHandler):
    """This is a server side API-"command" that takes no arguments and returns internal version
    """

    @classmethod
    def command_name(cls) -> str:
        """ The :meth:`.LobbyCommandHandler.command_name` method implementation
        """
        return "ping"

    @classmethod
    def command_model(cls) -> typing.Type[pydantic.BaseModel]:
        """ The :meth:`.LobbyCommandHandler.command_model` method implementation
        """
        return NullableModel

    async def exec(self) -> LobbyCommandResult:
        """ The :meth:`.LobbyCommandHandler.exec` method implementation
        """
        return LobbyStrFeedbackResult(
            str_result=f"pong... Version is {__version__}"
        )


@register_bellboy_command()
class BellBoyPingCommand(BellBoyCommandHandler):
    """This is a CLI "command" that returns client's version (if there wasn't any argument) or server's version (if
    URL and secret backend were set)
    """

    @classmethod
    def command_name(cls) -> str:
        """ The :meth:`.BellBoyCommandHandler.command_name` method implementation
        """
        return LobbyPingCommand.command_name()

    @classmethod
    def command_model(cls) -> typing.Type[pydantic.BaseModel]:
        """ The :meth:`.BellBoyCommandHandler.command_model` method implementation
        """
        return OptionalBellBoyCommandModel

    async def exec(self) -> LobbyCommandResult:
        """ The :meth:`.BellBoyCommandHandler.exec` method implementation
        """
        assert(isinstance(self._args, OptionalBellBoyCommandModel))

        if self._args.server is None:
            result = await LobbyPingCommand.prepare_command(NullableModel()).exec()
            result.str_result = f"Client response: {result.str_result}"  # type: ignore[union-attr]
            return result

        auth_data = self.auth_data(self._args.server.secret_backend, self._args.server.lobby_url)

        client = LobbyClient(self._args.server.lobby_url, auth_data.server_fingerprint, auth_data.token)
        result = await client.command_request(
            LobbyCommandRequest(
                name=LobbyPingCommand.command_name(),
                args=NullableModel().model_dump()
            )
        )

        result.str_result = f"Server response: {result.str_result}"  # type: ignore[union-attr]
        return result
