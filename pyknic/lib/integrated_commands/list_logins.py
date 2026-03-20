# -*- coding: utf-8 -*-
# pyknic/lib/integrated_commands/list_logins.py
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

from pyknic.lib.bellboy.app import register_bellboy_command, BellBoyCommandHandler
from pyknic.lib.bellboy.models import SecretBackendBellBoyCommandModel
from pyknic.lib.fastapi.models.lobby import LobbyCommandResult, LobbyListValueFeedbackResult


@register_bellboy_command()
class ListLoginsCommand(BellBoyCommandHandler):
    """List known logins
    """

    @classmethod
    def command_name(cls) -> str:
        """The :meth:`.BellBoyCommandHandler.command_name` method implementation"""
        return "list-login"

    @classmethod
    def command_model(cls) -> typing.Type[pydantic.BaseModel]:
        """The :meth:`.BellBoyCommandHandler.command_model` method implementation"""
        return SecretBackendBellBoyCommandModel

    @classmethod
    async def exec(cls, args: SecretBackendBellBoyCommandModel) -> LobbyCommandResult:  # type: ignore[override]
        """The :meth:`.BellBoyInternalCommand.exec_from_cli` method implementation
        """

        backend = cls.secret_backend(args.secret_backend)

        all_secrets = backend.get_secrets()
        return LobbyListValueFeedbackResult(
            list_result=[x for x in all_secrets.secrets.keys()]
        )
