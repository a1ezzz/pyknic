# -*- coding: utf-8 -*-
# pyknic/lib/fastapi/lobby_commands/ping.py
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

from pyknic.lib.fastapi.lobby import LobbyCommandDescriptorProto, register_command
from pyknic.lib.fastapi.models.lobby import LobbyCommand, LobbyCommandResult, LobbyStrFeedbackResult
from pyknic.version import __version__


@register_command()
class PingCommand(LobbyCommandDescriptorProto):
    """This command helps to check server's sanity."""

    @classmethod
    def command_name(cls) -> str:
        """:meth:`.LobbyCommandDescriptorProto.command_name` implementation."""
        return "ping"

    @classmethod
    def exec(cls, args: LobbyCommand) -> LobbyCommandResult:
        """Return pong-response message."""
        return LobbyStrFeedbackResult(result=f"pong... Server's version is {__version__}")
