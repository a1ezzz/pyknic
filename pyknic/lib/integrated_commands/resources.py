# -*- coding: utf-8 -*-
# pyknic/lib/integrated_commands/resources.py
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

# TODO: update tests!

import threading
import typing

import pydantic

from pyknic.lib.bellboy.app import BellBoyCommandHandler, register_bellboy_command, LobbyClient
from pyknic.lib.bellboy.models import GeneralBellBoyCommandModel
from pyknic.lib.fastapi.lobby import LobbyCommandHandler, register_lobby_command
from pyknic.lib.fastapi.models.base import NullableModel
from pyknic.lib.fastapi.models.lobby import LobbyCommandResult, LobbyKeyValueFeedbackResult, LobbyCommandRequest


@register_lobby_command()
class LobbyResourcesCommand(LobbyCommandHandler):
    """This is a server side API-"command" that takes no arguments and returns minor information about server's
    used resources
    """

    @classmethod
    def command_name(cls) -> str:
        """ The :meth:`.LobbyCommandHandler.command_name` method implementation
        """
        return "resources"

    @classmethod
    def command_model(cls) -> typing.Type[pydantic.BaseModel]:
        """ The :meth:`.LobbyCommandHandler.command_model` method implementation
        """
        return NullableModel

    @classmethod
    async def exec(cls, args: NullableModel) -> LobbyCommandResult:  # type: ignore[override]
        """ The :meth:`.LobbyCommandHandler.exec` method implementation
        """
        with open('/proc/self/statm') as mem_usage_fd:  # TODO: validate errors!
            statm = mem_usage_fd.readline()
            total, resident, shared = statm.split(' ')[:3]

        pythreads = threading.active_count()

        return LobbyKeyValueFeedbackResult(kv_result={
            "mem_total": int(total), "mem_resident": int(resident), "mem_shared": int(shared), "py_threads": pythreads
        })


@register_bellboy_command()
class BellBoyResourcesCommand(BellBoyCommandHandler):
    """This is a CLI "command" that returns minor information about server's used resources
    """

    @classmethod
    def command_name(cls) -> str:
        """ The :meth:`.BellBoyCommandHandler.command_name` method implementation
        """
        return LobbyResourcesCommand.command_name()

    @classmethod
    def command_model(cls) -> typing.Type[pydantic.BaseModel]:
        """ The :meth:`.BellBoyCommandHandler.command_model` method implementation
        """
        return GeneralBellBoyCommandModel

    @classmethod
    async def exec(cls, args: GeneralBellBoyCommandModel) -> LobbyCommandResult:  # type: ignore[override]
        """ The :meth:`.BellBoyCommandHandler.exec` method implementation
        """
        auth_data = cls.auth_data(args.secret_backend, args.lobby_url)

        client = LobbyClient(args.lobby_url, auth_data.server_fingerprint, auth_data.token)
        return await client.command_request(
            LobbyCommandRequest(
                name=LobbyResourcesCommand.command_name(),
                args=NullableModel().model_dump()
            )
        )
