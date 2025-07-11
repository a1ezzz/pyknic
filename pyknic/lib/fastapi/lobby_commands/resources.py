# -*- coding: utf-8 -*-
# pyknic/lib/fastapi/lobby_commands/resources.py
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

import threading


from pyknic.lib.fastapi.lobby import LobbyCommandDescriptorProto, register_command
from pyknic.lib.fastapi.models.lobby import LobbyCommand, LobbyCommandResult, LobbyKeyValueFeedbackResult


@register_command()
class ResourcesCommand(LobbyCommandDescriptorProto):
    """Returns minor information about server's used resources."""

    @classmethod
    def command_name(cls) -> str:
        """:meth:`.LobbyCommandDescriptorProto.command_name` implementation."""
        return "resources"

    @classmethod
    def exec(cls, args: LobbyCommand) -> LobbyCommandResult:
        """Return information about server's resources."""
        with open('/proc/self/statm') as mem_usage_fd:  # TODO: validate errors!
            statm = mem_usage_fd.readline()
            total, resident, shared = statm.split(' ')[:3]

        pythreads = threading.active_count()

        return LobbyKeyValueFeedbackResult(kv_result={
            "mem_total": total, "mem_resident": resident, "mem_shared": shared, "py_threads": pythreads
        })
