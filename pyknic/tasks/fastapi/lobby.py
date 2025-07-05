# -*- coding: utf-8 -*-
# pyknic/tasks/fastapi/lobby.py
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

import importlib
import typing
import secrets

import fastapi
import fastapi.security

from pyknic.lib.config import Config
from pyknic.lib.fastapi.models.base import NullableResponseModel
from pyknic.lib.registry import register_api
from pyknic.lib.fastapi.apps_registry import __default_fastapi_apps_registry__
from pyknic.lib.fastapi.models.lobby import LobbyCommandResult
from pyknic.lib.gettext import GetTextWrapper
from pyknic.lib.fastapi.base import BaseFastAPIApp
from pyknic.lib.fastapi.lobby import LobbyCommandError, __default_lobby_commands_registry__
from pyknic.lib.log import Logger


@register_api(__default_fastapi_apps_registry__, "lobby")
class LobbyApp(BaseFastAPIApp):

    __default_modules__ = {
        'pyknic.lib.fastapi.lobby_commands.ping'
    }

    def __init__(self, config: Config, translations: GetTextWrapper):
        BaseFastAPIApp.__init__(self, config, translations)

        self.__lobby_registry = __default_lobby_commands_registry__
        self.__translations = translations

    @classmethod
    def create_app(cls, fastapi_app: fastapi.FastAPI, config: Config, translations: GetTextWrapper) -> typing.Any:
        """ The :meth:`.FastAPIAppProto.create_app` method implementation
        """

        app = cls(config, translations)
        if not cls.secret_token(config):
            raise RuntimeError('Secret token is required')
        app.load_lobby_modules()

        fastapi_app.post(
            cls.main_lobby_path(config),
            status_code=200,
            response_model=LobbyCommandResult
        )(app.lobby_command)

        fastapi_app.get(
            cls.fingerprint_lobby_path(config),
            status_code=200,
            response_model=NullableResponseModel  # TODO: update fingerprint response
        )(app.fingerprint)

        return app

    def load_lobby_modules(self) -> None:
        modules_enabled = {str(x) for x in self.config()["pyknic"]["fastapi"]["lobby"]["modules"].iterate_list()}
        modules_enabled.update(self.__default_modules__)

        modules_list = list(modules_enabled)
        modules_list.sort()

        for module_name in modules_list:
            Logger.info(f'Import module "{module_name}" so commands will be loaded')
            importlib.import_module(module_name)

    async def fingerprint(self, request: fastapi.Request) -> NullableResponseModel:
        # TODO: implement
        return NullableResponseModel()

    async def login_with_bearer(self, request: fastapi.Request) -> None:
        # TODO: make it more secure
        #
        # And consider this:
        #
        # JWT and FastAPI:
        #   - https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/#handle-jwt-tokens
        # JWT known names:
        #   - https://pyjwt.readthedocs.io/en/stable/usage.html#registered-claim-names
        #   - https://en.wikipedia.org/wiki/JSON_Web_Token#Standard_fields
        #
        # JWT decode security warnings:
        #   - https://pyjwt.readthedocs.io/en/stable/api.html#jwt.decode

        http_bearer = fastapi.security.HTTPBearer()
        http_creds = await http_bearer(request)

        if http_creds:
            encoded_bearer = http_creds.credentials
            secret_token = self.secret_token(self.config())
            assert(secret_token)

            if secrets.compare_digest(encoded_bearer, secret_token):
                # note: compare_digest do comparison in a constant time
                return

        raise fastapi.HTTPException(
            status_code=fastapi.status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": 'Bearer realm="Token Required"'}
        )

    async def lobby_command(self, request: fastapi.Request) -> LobbyCommandResult:
        await self.login_with_bearer(request)

        try:
            if not await request.body():
                raise fastapi.HTTPException(
                    status_code=fastapi.status.HTTP_400_BAD_REQUEST, detail='Please submit JSON within request'
                )

            data = await request.json()
            command, args = self.__lobby_registry.deserialize_command(data)

            return command.exec(args)
        except LobbyCommandError as e:
            raise fastapi.HTTPException(status_code=fastapi.status.HTTP_400_BAD_REQUEST, detail=str(e))

    @classmethod
    def main_lobby_path(cls, config: Config) -> str:
        return str(config["pyknic"]["fastapi"]["lobby"]["main_url_path"])

    @classmethod
    def fingerprint_lobby_path(cls, config: Config) -> str:
        return str(config["pyknic"]["fastapi"]["lobby"]["fingerprint_url_path"])

    @classmethod
    def secret_token(cls, config: Config) -> typing.Optional[str]:
        token = config["pyknic"]["fastapi"]["lobby"]["secret_token"]
        return str(token) if not token.is_none() else None
