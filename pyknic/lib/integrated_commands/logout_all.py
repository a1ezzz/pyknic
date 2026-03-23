# -*- coding: utf-8 -*-
# pyknic/lib/integrated_commands/logout_all.py
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
from pyknic.lib.fastapi.models.lobby import LobbyCommandResult, LobbyStrFeedbackResult


@register_bellboy_command()
class LogoutAllCommand(BellBoyCommandHandler):
    """ Forget all known credentials
    """

    @classmethod
    def command_name(cls) -> str:
        """The :meth:`.BellBoyCommandHandler.command_name` method implementation"""
        return "logout-all"

    @classmethod
    def command_model(cls) -> typing.Type[pydantic.BaseModel]:
        """The :meth:`.BellBoyCommandHandler.command_model` method implementation"""
        return SecretBackendBellBoyCommandModel

    async def exec(self) -> LobbyCommandResult:
        """The :meth:`.BellBoyInternalCommand.exec_from_cli` method implementation
        """
        assert(isinstance(self._args, SecretBackendBellBoyCommandModel))

        secret_backend = self.secret_backend(self._args.secret_backend)

        count = secret_backend.get_secrets().secrets.keys()
        secret_backend.purge()
        return LobbyStrFeedbackResult(str_result=f'Login credentials for {count} sites has been forgotten')
