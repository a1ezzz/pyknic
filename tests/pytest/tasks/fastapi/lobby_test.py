# -*- coding: utf-8 -*-

import asyncio
import base64
import json
import io
import pathlib

import aiohttp
import fastapi
import jwt
import pytest
import yaml

from pyknic.lib.crypto.rsa import RSAPublicKey
from pyknic.tasks.fastapi.lobby import LobbyApp
from pyknic.lib.gettext import GetTextWrapper
from pyknic.lib.config import Config
from pyknic.lib.path import root_path
from pyknic.lib.fastapi.headers import FastAPIHeaders
from pyknic.lib.fastapi.models.lobby import LobbyStrFeedbackResult, LobbyPublicKeyModel, LobbyEncodedJWT
from pyknic.lib.fastapi.lobby import URLPath

from fixtures.asyncio import pyknic_async_test
from fixtures.fastapi import AsyncFastAPIFixture


class TestLobbyApp:

    __lobby_yaml__ = """
    pyknic:
        fastapi:
            lobby:
                aaa_policies:
                    allow_all:
                        handler: trust  # no auth!
                        handler_settings:
                            as_user: 'admin'
                        allowed_commands: []  # list of allowed commands
                        denied_commands: []  # list of denied commands

                    token_test:
                        handler: bearer_static_token
                        handler_settings:
                            secret_token: 'some-token!'
                            as_user: 'admin'
                        allowed_commands: []  # list of allowed commands
                        denied_commands: []  # list of denied commands
    """

    def test_config(self, gettext: GetTextWrapper) -> None:
        fastapi_server = fastapi.FastAPI()

        with open(root_path / 'tasks/fastapi/config.yaml') as f:
            default_config = Config(file_obj=f)
        self.gettext = GetTextWrapper(root_path / 'locales')

        with pytest.raises(ValueError):
            # aaa settings are required
            LobbyApp.create_app(fastapi_server, default_config, gettext)

        config = Config()
        config.merge_config(default_config)
        config.merge_config(Config(file_obj=io.StringIO(self.__lobby_yaml__)))

    @AsyncFastAPIFixture.base_config(LobbyApp, __lobby_yaml__)
    @pyknic_async_test
    async def test_public_key(
        self,
        module_event_loop: asyncio.AbstractEventLoop,
        fastapi_module_fixture: AsyncFastAPIFixture,
    ) -> None:
        lobby_path = fastapi_module_fixture.app_config["pyknic"]["fastapi"]["lobby"]["main_url_path"]
        lobby_url = f'http://localhost:8000{lobby_path}/{URLPath.public_key.value}'

        session = aiohttp.ClientSession()
        async with session.get(lobby_url) as response:
            assert(response.status == 200)
            public_key = LobbyPublicKeyModel.model_validate(await response.json())
            _ = RSAPublicKey.import_pem(public_key.pem.encode('ascii'))  # check that everything is ok

    @AsyncFastAPIFixture.base_config(LobbyApp, __lobby_yaml__)
    @pyknic_async_test
    async def test_not_persistent_public_key(
        self,
        module_event_loop: asyncio.AbstractEventLoop,
        fastapi_module_fixture: AsyncFastAPIFixture,
    ) -> None:

        lobby_path = fastapi_module_fixture.app_config["pyknic"]["fastapi"]["lobby"]["main_url_path"]
        base_lobby_url = f'http://localhost:8000{lobby_path}'

        ping_request = '{"name": "ping", "args": {}, "client_version": "some-version", "plugin_version": "version"}'

        session = aiohttp.ClientSession()

        async with session.get(f'{base_lobby_url}/{URLPath.public_key.value}') as response:
            assert(response.status == 200)
            lobby_public_key = LobbyPublicKeyModel.model_validate(await response.json())

        async with session.post(f'{base_lobby_url}/{URLPath.login_trust.value}') as response:
            assert(response.status == 200)
            lobby_jwt = LobbyEncodedJWT.model_validate(await response.json())

            # just to check signature
            _ = jwt.decode(
                lobby_jwt.token_data,
                lobby_public_key.pem,
                algorithms=['RS256'],
                options={"verify_aud": False}  # this is OK, since we check signature
            )

        headers = {
            'Authorization': f'Bearer {lobby_jwt.token_data}',
            'Content-Type': 'application/json',
        }
        async with session.post(f'http://localhost:8000{lobby_path}', headers=headers, data=ping_request) as response:
            assert(response.status == 200)

        await fastapi_module_fixture.flush_async(module_event_loop)
        fastapi_module_fixture.setup_fastapi(LobbyApp, self.__lobby_yaml__)

        async with session.post(f'http://localhost:8000{lobby_path}', headers=headers, data=ping_request) as response:
            assert(response.status in [401, 403])

        async with session.post(f'{base_lobby_url}/{URLPath.login_trust.value}') as response:
            # just to check that authorization works

            assert(response.status == 200)
            lobby_jwt = LobbyEncodedJWT.model_validate(await response.json())

            with pytest.raises(jwt.DecodeError):
                # but signature has been changed
                _ = jwt.decode(
                    lobby_jwt.token_data,
                    lobby_public_key.pem,
                    algorithms=['RS256'],
                    options={"verify_aud": False}  # this is OK, since we check signature
                )

    @AsyncFastAPIFixture.base_config(LobbyApp, __lobby_yaml__)
    @pyknic_async_test
    async def test_persistent_public_key(
        self,
        tmp_path: pathlib.Path,
        module_event_loop: asyncio.AbstractEventLoop,
        fastapi_module_fixture: AsyncFastAPIFixture,
    ) -> None:

        private_key_location = tmp_path / 'private_key.pem'
        base_config = yaml.safe_load(self.__lobby_yaml__)
        base_config["pyknic"]["fastapi"]["lobby"]["private_key_location"] = str(private_key_location)

        extra_config_txt = yaml.dump(base_config)

        await fastapi_module_fixture.flush_async(module_event_loop)
        fastapi_module_fixture.setup_fastapi(LobbyApp, extra_config_txt)

        lobby_path = fastapi_module_fixture.app_config["pyknic"]["fastapi"]["lobby"]["main_url_path"]
        base_lobby_url = f'http://localhost:8000{lobby_path}'

        ping_request = '{"name": "ping", "args": {}, "client_version": "some-version", "plugin_version": "version"}'

        session = aiohttp.ClientSession()

        async with session.get(f'{base_lobby_url}/{URLPath.public_key.value}') as response:
            assert(response.status == 200)
            lobby_public_key = LobbyPublicKeyModel.model_validate(await response.json())

        async with session.post(f'{base_lobby_url}/{URLPath.login_trust.value}') as response:
            assert(response.status == 200)
            lobby_jwt = LobbyEncodedJWT.model_validate(await response.json())

            # just to check signature
            _ = jwt.decode(
                lobby_jwt.token_data,
                lobby_public_key.pem,
                algorithms=['RS256'],
                options={"verify_aud": False}  # this is OK, since we check signature
            )

        headers = {
            'Authorization': f'Bearer {lobby_jwt.token_data}',
            'Content-Type': 'application/json',
        }
        async with session.post(f'http://localhost:8000{lobby_path}', headers=headers, data=ping_request) as response:
            assert(response.status == 200)

        await fastapi_module_fixture.flush_async(module_event_loop)
        fastapi_module_fixture.setup_fastapi(LobbyApp, extra_config_txt)

        async with session.post(f'http://localhost:8000{lobby_path}', headers=headers, data=ping_request) as response:
            assert(response.status == 200)

        async with session.post(f'{base_lobby_url}/{URLPath.login_trust.value}') as response:
            # just to check that authorization works

            assert(response.status == 200)
            lobby_jwt = LobbyEncodedJWT.model_validate(await response.json())

            # signature check works too
            _ = jwt.decode(
                lobby_jwt.token_data,
                lobby_public_key.pem,
                algorithms=['RS256'],
                options={"verify_aud": False}  # this is OK, since we check signature
            )

    @AsyncFastAPIFixture.base_config(LobbyApp, __lobby_yaml__)
    @pyknic_async_test
    async def test(
        self,
        module_event_loop: asyncio.AbstractEventLoop,
        fastapi_module_fixture: AsyncFastAPIFixture,
    ) -> None:
        lobby_path = fastapi_module_fixture.app_config["pyknic"]["fastapi"]["lobby"]["main_url_path"]
        public_key_url = f'http://localhost:8000{lobby_path}/{URLPath.public_key.value}'

        session = aiohttp.ClientSession()
        async with session.get(public_key_url) as response:
            public_key_model = LobbyPublicKeyModel.model_validate(await response.json())

        async with session.post(f'http://localhost:8000{lobby_path}') as response:
            assert(response.status in (403, 401))

        headers = {
            'Authorization': 'Bearer invalid-token',  # foo:bar
        }
        async with session.post(
            f'http://localhost:8000{lobby_path}/{URLPath.login_bearer.value}',
            headers=headers
        ) as response:
            assert(response.status in (403, 401))

        async with session.post(f'http://localhost:8000{lobby_path}', headers=headers) as response:
            # no body request
            assert(response.status == 422)

        async with session.post(f'http://localhost:8000{lobby_path}', headers=headers, data='{}') as response:
            # invalid body request
            assert(response.status == 422)

        async with session.post(f'http://localhost:8000{lobby_path}/{URLPath.login_trust.value}') as response:
            assert(response.status == 200)
            jwt_json = await response.json()

        headers = {
            'Authorization': f'Bearer {jwt_json["token_data"]}',  # foo:bar
            'Content-Type': 'application/json',
        }
        ping_request = '{"name": "ping", "args": {}, "client_version": "some-version", "plugin_version": "version"}'
        async with session.post(f'http://localhost:8000{lobby_path}', headers=headers, data=ping_request) as response:
            assert(response.status == 200)

            pk_signing_str = response.headers[FastAPIHeaders.signature.value]
            pk_signing_str_bin = base64.b64decode(pk_signing_str)
            response_data = await response.content.read()
            feedback = LobbyStrFeedbackResult.model_validate(json.loads(response_data))
            assert(len(feedback.str_result) > 0)

            public_key = RSAPublicKey.import_pem(public_key_model.pem.encode('ascii'))

            _ = public_key.verify(  # this does not raise an exception
                pk_signing_str_bin,
                response_data,
                fastapi_module_fixture.app_config["pyknic"]["fastapi"]["lobby"]["response_signing_hash"].as_str()
            )
