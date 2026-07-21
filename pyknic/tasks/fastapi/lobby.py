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


import base64
import dataclasses
import os
import pathlib
import typing

import fastapi
import fastapi.encoders
import fastapi.responses
import fastapi.security

import jwt

from pyknic.lib.config import Config
from pyknic.lib.crypto.rsa import RSAPrivateKey
from pyknic.lib.registry import register_api
from pyknic.lib.fastapi.apps_registry import __default_fastapi_apps_registry__
from pyknic.lib.fastapi.models.lobby import LobbyPublicKeyModel, LobbyCommandRequest, LobbyEncodedJWT, LobbyJWTPayload
from pyknic.lib.fastapi.models.lobby import LobbyCommandResult
from pyknic.lib.gettext import GetTextWrapper
from pyknic.lib.fastapi.base import BaseFastAPIApp
from pyknic.lib.fastapi.lobby import LobbyCommandError, __default_lobby_commands_registry__, URLPath
from pyknic.lib.path import root_path
from pyknic.lib.fastapi.headers import FastAPIHeaders
from pyknic.lib.log import Logger
from pyknic.lib.fastapi.fastapi_aaa import __default_fastapi_aaa_registry__, FastAPIIdentity
from pyknic.lib.fastapi.fastapi_aaa import AuthenticationProviderProto

from fastapi.security import HTTPBasic, HTTPBearer, HTTPAuthorizationCredentials

# TODO: document the code!
# TODO: test the code!

# TODO: implement registry of issued jwt (by theirs id)
# TODO: implement jwt black lists
# TODO: implement jwt revocation api


@dataclasses.dataclass
class LobbyAAAPolicy:
    policy_name: str
    authentication_handler: AuthenticationProviderProto
    allowed_commands: typing.List[str]
    denied_commands: typing.List[str]


@register_api(__default_fastapi_apps_registry__, "lobby")
class LobbyApp(BaseFastAPIApp):
    """This web-app executes commands on remote server."""

    __default_modules__ = {
        'pyknic.lib.integrated_commands.ping',
        'pyknic.lib.integrated_commands.resources',
    }

    def __init__(self, config: Config, translations: GetTextWrapper):
        """Create a new web-app.

        :param config: config with which this app should be initialized
        :param translations: gettext access
        """

        BaseFastAPIApp.__init__(self, config, translations)

        self.__lobby_registry = __default_lobby_commands_registry__
        self.__translations = translations

        self.__aaa_policies: typing.Dict[str, LobbyAAAPolicy] = dict()
        self.__private_key_size = self.config()["pyknic"]["fastapi"]["lobby"]["private_key_default_size"].as_int()
        self.__private_key: typing.Optional[RSAPrivateKey] = None

        self.__signing_hash = self.config()["pyknic"]["fastapi"]["lobby"]["response_signing_hash"].as_str()

        self.__jwt_algorithm = self.config()["pyknic"]["fastapi"]["lobby"]["jwt"]["algorithm"].as_str()
        self.__jwt_audience = self.config()["pyknic"]["fastapi"]["lobby"]["jwt"]["audience"].as_str()
        self.__jwt_leeway = self.config()["pyknic"]["fastapi"]["lobby"]["jwt"]["leeway"].as_int()
        self.__jwt_ttl = self.config()["pyknic"]["fastapi"]["lobby"]["jwt"]["ttl"].as_int()

        self.__lobby_host = self.config()["pyknic"]["fastapi"]["uvicorn_host"].as_str()
        self.__lobby_port = self.config()["pyknic"]["fastapi"]["uvicorn_port"].as_int()

    def load_private_key(self) -> None:
        pk_location_opt = self.config()["pyknic"]["fastapi"]["lobby"]["private_key_location"]

        if pk_location_opt.is_none():
            self.__private_key = RSAPrivateKey.generate(self.__private_key_size)
        else:
            pk_location = pk_location_opt.as_str()

            pk_path = pathlib.Path(pk_location)
            if not pk_path.is_absolute():
                pk_path = root_path / pk_path

            if pk_path.exists(follow_symlinks=False):
                pk_stat = pk_path.stat(follow_symlinks=False)
                pk_permissions = pk_stat.st_mode & 0o7777
                if pk_permissions != 0o0600:
                    raise ValueError(
                        f'Invalid permission for the file {str(pk_path)} should be -- 0600'
                    )

                with pk_path.open('rb') as f:
                    self.__private_key = RSAPrivateKey.import_pem(f.read())
            else:
                pk = RSAPrivateKey.generate(self.__private_key_size)

                pk_fd = os.open(pk_path, os.O_WRONLY | os.O_CREAT, 0o0600)
                with os.fdopen(pk_fd, 'wb') as f:
                    pk_pem = pk.export_pem()
                    f.write(pk_pem)

                self.__private_key = pk

    def setup_aaa(self) -> None:
        aaa_config = self.config()["pyknic"]["fastapi"]["lobby"]["aaa_policies"]

        self.__aaa_policies = dict()

        for policy_name in aaa_config.properties():
            policy_settings = aaa_config[policy_name]

            handler_name = policy_settings['handler'].as_str()
            handler_settings = policy_settings['handler_settings']

            handler_cls = __default_fastapi_aaa_registry__.get(handler_name)

            policy = LobbyAAAPolicy(
                policy_name=policy_name,
                authentication_handler=handler_cls.create(policy_name, handler_settings),
                allowed_commands=[x.as_str() for x in policy_settings['allowed_commands'].iterate_list()],
                denied_commands=[x.as_str() for x in policy_settings['denied_commands'].iterate_list()]
            )

            self.__aaa_policies[policy_name] = policy

        if not self.__aaa_policies:
            raise ValueError('Please, configure one "aaa" policy at least!')

    @classmethod
    def create_app(cls, fastapi_app: fastapi.FastAPI, config: Config, translations: GetTextWrapper) -> typing.Any:
        """ The :meth:`.FastAPIAppProto.create_app` method implementation
        """

        app = cls(config, translations)

        app.load_private_key()
        app.setup_aaa()

        fastapi_app.get(
            cls.lobby_public_key_path(config),
            status_code=200,
            response_model=LobbyPublicKeyModel
        )(app.public_key)

        fastapi_app.post(
            cls.lobby_login_trust_path(config),
            status_code=200,
            response_model=LobbyEncodedJWT
        )(app.login_with_trust)

        fastapi_app.post(
            cls.lobby_login_bearer_path(config),
            status_code=200,
            response_model=LobbyEncodedJWT
        )(app.login_with_bearer)

        fastapi_app.post(
            cls.lobby_login_basic_path(config),
            status_code=200,
            response_model=LobbyEncodedJWT
        )(app.login_with_basic_auth)

        fastapi_app.post(
            cls.lobby_main_path(config),
            status_code=200,
            response_model=LobbyCommandResult
        )(app.lobby_command)

        return app

    def __sign_result(self, json_data: str) -> fastapi.Response:
        """Sign request result.

        :param json_data: API result to sign
        """
        assert(self.__private_key)

        response_headers = dict()
        signature = self.__private_key.sign(json_data.encode(), self.__signing_hash)
        response_headers[FastAPIHeaders.signature.value] = base64.b64encode(signature).decode('ascii')

        return fastapi.Response(content=json_data, media_type="application/json", headers=response_headers)

    async def public_key(self) -> LobbyPublicKeyModel:
        assert(self.__private_key)
        return LobbyPublicKeyModel(
            pem=self.__private_key.public_key().export_pem().decode('ascii'),
            sign_hash_method=self.__signing_hash
        )

    def __generate_auth_token(self, user_id: FastAPIIdentity, policy_name: str) -> LobbyEncodedJWT:

        assert(self.__private_key)

        jwt_payload = LobbyJWTPayload.generate(
            ttl=self.__jwt_ttl,
            subject=user_id.identity,
            audience=self.__jwt_audience,
            lobby_host=self.__lobby_host,
            lobby_port=self.__lobby_port,
            policy_name=policy_name
        )

        jwt_payload_dict = jwt_payload.model_dump()

        token_data = jwt.encode(
            jwt_payload_dict,
            self.__private_key.export_pem().decode('ascii'),
            algorithm=self.__jwt_algorithm
        )

        return LobbyEncodedJWT(token_data=token_data)

    async def __login(
        self, request: fastapi.Request, handler: typing.Optional[typing.Type[fastapi.security.http.HTTPBase]] = None
    ) -> LobbyEncodedJWT:

        suitable_policies = [
            x for x in self.__aaa_policies.values() if (
                (x.authentication_handler.fastapi_handler() is None and handler is None) or
                (x.authentication_handler.fastapi_handler() == handler)
            )
        ]

        if not suitable_policies:
            err_msg = 'No suitable methods enabled!'
            Logger.error(err_msg)
            raise fastapi.HTTPException(
                status_code=fastapi.status.HTTP_400_BAD_REQUEST,
                detail=err_msg,
            )

        for policy in suitable_policies:
            user_id = await policy.authentication_handler.authenticate(request)
            if user_id is not None:
                return self.__generate_auth_token(user_id, policy.policy_name)

        err_msg = 'Incorrect authentication data. Secret is wrong!'
        Logger.error(err_msg)
        raise fastapi.HTTPException(
            status_code=fastapi.status.HTTP_401_UNAUTHORIZED,
            detail=err_msg,
        )

    async def login_with_trust(self, request: fastapi.Request) -> LobbyEncodedJWT:
        return await self.__login(request)

    async def login_with_bearer(
        self,
        request: fastapi.Request,
        auth: typing.Annotated[HTTPAuthorizationCredentials, fastapi.Depends(HTTPBearer())]
    ) -> LobbyEncodedJWT:
        return await self.__login(request, fastapi.security.HTTPBearer)

    async def login_with_basic_auth(
        self,
        request: fastapi.Request,
        auth: typing.Annotated[HTTPAuthorizationCredentials, fastapi.Depends(HTTPBasic())]
    ) -> LobbyEncodedJWT:
        return await self.__login(request, fastapi.security.HTTPBasic)

    async def lobby_command(
        self,
        command_request: LobbyCommandRequest,
        auth: typing.Annotated[HTTPAuthorizationCredentials, fastapi.Depends(HTTPBearer())]
    ) -> fastapi.Response:
        """Process command execution request.

        :param command_request: command request
        :param auth: authentication parameters
        """

        assert(self.__private_key)

        try:
            decoded_jwt = jwt.decode(
                auth.credentials,
                self.__private_key.public_key().export_pem().decode('ascii'),
                algorithms=[self.__jwt_algorithm],
                audience=self.__jwt_audience,
                issuer=LobbyJWTPayload.issuer(self.__lobby_host, self.__lobby_port),
                options={
                    "require": ["exp", "iat", "iss", "aud", "jti", "sub"],
                    "strict_aud": True,
                    "verify_signature": True,
                },
                leeway=self.__jwt_leeway,
            )

        except jwt.DecodeError:
            err_msg = 'Invalid JWT. Looks like a bearer token is not JWT at all'
            Logger.error(err_msg)
            raise fastapi.HTTPException(
                    status_code=fastapi.status.HTTP_401_UNAUTHORIZED,
                    detail=err_msg,
                    headers={"WWW-Authenticate": 'Bearer realm="Token Required"'}
                )
        except jwt.ExpiredSignatureError:
            err_msg = 'Invalid JWT. JWT has been expired!'
            Logger.error(err_msg)
            raise fastapi.HTTPException(
                status_code=fastapi.status.HTTP_401_UNAUTHORIZED,
                detail=err_msg,
                headers={"WWW-Authenticate": 'Bearer realm="Token Required"'}
            )
        except jwt.InvalidIssuerError:
            err_msg = 'Invalid JWT. Issuer is incorrect!'
            Logger.error(err_msg)
            raise fastapi.HTTPException(
                status_code=fastapi.status.HTTP_401_UNAUTHORIZED,
                detail=err_msg,
                headers={"WWW-Authenticate": 'Bearer realm="Token Required"'}
            )
        except jwt.InvalidAudienceError:
            err_msg = 'Invalid JWT. Audience is incorrect!'
            Logger.error(err_msg)
            raise fastapi.HTTPException(
                status_code=fastapi.status.HTTP_401_UNAUTHORIZED,
                detail=err_msg,
                headers={"WWW-Authenticate": 'Bearer realm="Token Required"'}
            )

        jwt_payload: LobbyJWTPayload = LobbyJWTPayload.model_validate(decoded_jwt)

        Logger.info(f'User "{jwt_payload.sub}" authenticated for lobby command with "{jwt_payload.policy_name}" policy')

        # TODO: check versions in client requests and the server's one. If they are differ, then result should have
        #   a warning about it. In future there may be plugins that has versions other than pyknic's

        try:

            policy = self.__aaa_policies[jwt_payload.policy_name]

            if command_request.name in policy.denied_commands:
                err_msg = f'The "{command_request.name}" command is disabled by the policy "{policy.policy_name}"'
                Logger.error(err_msg)
                raise fastapi.HTTPException(
                    status_code=fastapi.status.HTTP_403_FORBIDDEN,
                    detail=err_msg
                )

            if policy.allowed_commands and command_request.name not in policy.allowed_commands:
                err_msg = f'The "{command_request.name}" command is not allowed by the policy "{policy.policy_name}"'
                Logger.error(err_msg)
                raise fastapi.HTTPException(
                    status_code=fastapi.status.HTTP_403_FORBIDDEN,
                    detail=err_msg
                )

            command_handler = self.__lobby_registry.get(command_request.name)
            command_args_class = command_handler.command_model()
            command_args = command_args_class.model_validate(command_request.args)

            command_result = await command_handler.exec(command_args)
            json_result = command_result.model_dump_json()
            return self.__sign_result(json_result)

        except LobbyCommandError as e:
            Logger.error(f'Command execution error: {e}')
            raise fastapi.HTTPException(status_code=fastapi.status.HTTP_400_BAD_REQUEST, detail=str(e))

    @classmethod
    def lobby_main_path(cls, config: Config) -> str:
        """Return path for command execution requests."""
        return str(config["pyknic"]["fastapi"]["lobby"]["main_url_path"])

    @classmethod
    def lobby_public_key_path(cls, config: Config) -> str:
        return f'{str(config["pyknic"]["fastapi"]["lobby"]["main_url_path"])}/{URLPath.public_key.value}'

    @classmethod
    def lobby_login_basic_path(cls, config: Config) -> str:
        return f'{str(config["pyknic"]["fastapi"]["lobby"]["main_url_path"])}/{URLPath.login_basic.value}'

    @classmethod
    def lobby_login_bearer_path(cls, config: Config) -> str:
        return f'{str(config["pyknic"]["fastapi"]["lobby"]["main_url_path"])}/{URLPath.login_bearer.value}'

    @classmethod
    def lobby_login_trust_path(cls, config: Config) -> str:
        return f'{str(config["pyknic"]["fastapi"]["lobby"]["main_url_path"])}/{URLPath.login_trust.value}'
