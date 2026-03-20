# -*- coding: utf-8 -*-
# pyknic/lib/integrated_commands/login.py
#
# Copyright (C) 2026 the pyknic authors and contributors
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
import rich.prompt

from pyknic.lib.bellboy.app import register_bellboy_command, BellBoyCommandHandler, LobbyClient
from pyknic.lib.bellboy.models import GeneralBellBoyCommandModel
from pyknic.lib.fastapi.models.lobby import LobbyCommandResult, LobbyCommandRequest, LobbyStrFeedbackResult
from pyknic.lib.integrated_commands.ping import LobbyPingCommand


@register_bellboy_command()
class LoginCommand(BellBoyCommandHandler):
    """Login to a custom lobby server
    """

    @classmethod
    def command_name(cls) -> str:
        """The :meth:`.BellBoyCommandHandler.command_name` method implementation"""
        return "login"

    @classmethod
    def command_model(cls) -> typing.Type[pydantic.BaseModel]:
        """The :meth:`.BellBoyCommandHandler.command_model` method implementation"""
        return GeneralBellBoyCommandModel

    @classmethod
    async def exec(cls, args: GeneralBellBoyCommandModel) -> LobbyCommandResult:  # type: ignore[override]
        """The :meth:`.BellBoyInternalCommand.exec_from_cli` method implementation
        """

        secret_token = rich.prompt.Prompt.ask('Secret token', password=True)  # TODO: this looks pretty ugly =(
        # there should be direct interaction with CLI

        server_fingerprint = await LobbyClient.fingerprint(args.lobby_url)

        # just to check that auth is ok
        await LobbyClient(args.lobby_url, server_fingerprint, secret_token).command_request(
            LobbyCommandRequest(
                name=LobbyPingCommand.command_name(),
                args=LobbyPingCommand.command_model()().model_dump()
            )
        )

        secret_backend = cls.secret_backend(args.secret_backend)
        secret_backend.set_secret(args.lobby_url, server_fingerprint, secret_token)
        return LobbyStrFeedbackResult(str_result=f'Successful login to the {args.lobby_url}')
