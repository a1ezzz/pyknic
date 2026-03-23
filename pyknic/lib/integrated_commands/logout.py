# -*- coding: utf-8 -*-
# pyknic/lib/integrated_commands/logout.py
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

import contextlib
import typing

import pydantic

from pyknic.lib.bellboy.app import register_bellboy_command, BellBoyCommandHandler
from pyknic.lib.bellboy.models import GeneralBellBoyCommandModel
from pyknic.lib.fastapi.models.lobby import LobbyCommandResult, LobbyStrFeedbackResult


@register_bellboy_command()
class LogoutCommand(BellBoyCommandHandler):
    """ Forget known credential
    """

    @classmethod
    def command_name(cls) -> str:
        """The :meth:`.BellBoyCommandHandler.command_name` method implementation"""
        return "logout"

    @classmethod
    def command_model(cls) -> typing.Type[pydantic.BaseModel]:
        """The :meth:`.BellBoyCommandHandler.command_model` method implementation"""
        return GeneralBellBoyCommandModel

    async def exec(self) -> LobbyCommandResult:
        """The :meth:`.BellBoyInternalCommand.exec_from_cli` method implementation
        """
        assert(isinstance(self._args, GeneralBellBoyCommandModel))

        secret_backend = self.secret_backend(self._args.secret_backend)

        with contextlib.suppress(KeyError):
            secret_backend.pop_secret(self._args.lobby_url)
            return LobbyStrFeedbackResult(
                str_result=f'Login credential for the {self._args.lobby_url} site has been forgotten'
            )
        return LobbyStrFeedbackResult(
            str_result=f'There is no credential for the {self._args.lobby_url} site'
        )
