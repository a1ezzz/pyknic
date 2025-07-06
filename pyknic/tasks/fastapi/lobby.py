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

import importlib
import json
import typing
import secrets

import fastapi
import fastapi.encoders
import fastapi.responses
import fastapi.security

from pyknic.lib.config import Config
from pyknic.lib.registry import register_api
from pyknic.lib.fastapi.apps_registry import __default_fastapi_apps_registry__
from pyknic.lib.fastapi.models.lobby import LobbyServerFingerprint
from pyknic.lib.gettext import GetTextWrapper
from pyknic.lib.fastapi.base import BaseFastAPIApp
from pyknic.lib.fastapi.lobby import LobbyCommandError, __default_lobby_commands_registry__
from pyknic.lib.fastapi.lobby_fingerprint import LobbyFingerprint
from pyknic.lib.fastapi.headers import FastAPIHeaders
from pyknic.lib.log import Logger


@register_api(__default_fastapi_apps_registry__, "lobby")
class LobbyApp(BaseFastAPIApp):
    """This web-app executes commands on remote server."""

    __default_modules__ = {
        'pyknic.lib.fastapi.lobby_commands.ping'
    }

    def __init__(self, config: Config, translations: GetTextWrapper):
        """Create a new web-app.

        :param config: config with which this app should be initialized
        :param translations: gettext access
        """

        BaseFastAPIApp.__init__(self, config, translations)

        self.__lobby_registry = __default_lobby_commands_registry__
        self.__translations = translations

        # TODO: make fingerprint survive restarts
        self.__fingerprint = LobbyFingerprint.generate_fingerprint()

    @classmethod
    def create_app(cls, fastapi_app: fastapi.FastAPI, config: Config, translations: GetTextWrapper) -> typing.Any:
        """ The :meth:`.FastAPIAppProto.create_app` method implementation
        """

        app = cls(config, translations)
        if not cls.secret_token(config):
            raise RuntimeError('Secret token is required')
        app.load_lobby_modules()

        fastapi_app.post(
            cls.lobby_main_path(config),
            status_code=200
        )(app.lobby_command)

        fastapi_app.get(
            cls.lobby_fingerprint_path(config),
            status_code=200,
            response_model=LobbyServerFingerprint
        )(app.fingerprint)

        fastapi_app.get(
            cls.lobby_contexts_path(config),
            status_code=200,
            response_model=typing.List[str]
        )(app.lobby_contexts)

        return app

    def load_lobby_modules(self) -> None:
        """Import required modules so theirs commands may be used within this web-app."""
        modules_enabled = {str(x) for x in self.config()["pyknic"]["fastapi"]["lobby"]["modules"].iterate_list()}
        modules_enabled.update(self.__default_modules__)

        modules_list = list(modules_enabled)
        modules_list.sort()

        for module_name in modules_list:
            Logger.info(f'Import module "{module_name}" so commands will be loaded')
            importlib.import_module(module_name)

    async def lobby_contexts(self, request: fastapi.Request) -> typing.List[str]:
        await self.login_with_bearer(request)
        return list(self.__lobby_registry.list_contexts())

    async def fingerprint(self, request: fastapi.Request) -> LobbyServerFingerprint:
        return LobbyServerFingerprint(fingerprint=str(self.__fingerprint))

    async def login_with_bearer(self, request: fastapi.Request) -> None:
        """Authenticate request with bearer token.

        :param request: request with bearer token
        """
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

    async def lobby_command(self, request: fastapi.Request, response: fastapi.Response) -> fastapi.Response:
        """Process command execution request.

        :param request: request with command request
        """
        await self.login_with_bearer(request)

        try:
            if not await request.body():
                raise fastapi.HTTPException(
                    status_code=fastapi.status.HTTP_400_BAD_REQUEST, detail='Please submit JSON within request'
                )

            data = await request.json()
            command, args = self.__lobby_registry.deserialize_command(data)

            command_result = command.exec(args)
            json_ready_result = fastapi.encoders.jsonable_encoder(command_result)
            json_result = json.dumps(json_ready_result)

            signature = self.__fingerprint.sign(json_result.encode(), encode_base64=True)

            response_headers = dict()
            response_headers[FastAPIHeaders.fingerprint.value] = signature.decode('ascii')

            return fastapi.Response(content=json_result, media_type="application/json", headers=response_headers)

        except LobbyCommandError as e:
            raise fastapi.HTTPException(status_code=fastapi.status.HTTP_400_BAD_REQUEST, detail=str(e))

    @classmethod
    def lobby_main_path(cls, config: Config) -> str:
        """Return path for command execution requests."""
        return str(config["pyknic"]["fastapi"]["lobby"]["main_url_path"])

    @classmethod
    def lobby_fingerprint_path(cls, config: Config) -> str:
        """Return path for fingerprint request."""
        return str(config["pyknic"]["fastapi"]["lobby"]["fingerprint_url_path"])

    @classmethod
    def lobby_contexts_path(cls, config: Config) -> str:
        """Return path for fingerprint request."""
        return str(config["pyknic"]["fastapi"]["lobby"]["contexts_url_path"])

    @classmethod
    def secret_token(cls, config: Config) -> typing.Optional[str]:
        """Return secret token that is used for authentication."""
        token = config["pyknic"]["fastapi"]["lobby"]["secret_token"]
        return str(token) if not token.is_none() else None
