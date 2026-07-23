# -*- coding: utf-8 -*-

import asyncio
import pathlib
import typing

import pytest
from _pytest.monkeypatch import MonkeyPatch

from pyknic.lib.integrated_commands.login import LoginCommand, LoginCommandModel, AuthenticationMode, SecretReadModel
from pyknic.lib.bellboy.models import MainBellBoyCommandModel, SecretBackendType
from pyknic.lib.fastapi.models.lobby import LobbyStrFeedbackResult
from pyknic.tasks.fastapi.lobby import LobbyApp

from fixtures.asyncio import pyknic_async_test
from fixtures.fastapi import AsyncFastAPIFixture


class TestLoginCommand:

    __trust_lobby_yaml__ = """
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
    """

    __token_lobby_yaml__ = """
        pyknic:
            fastapi:
                lobby:
                    aaa_policies:
                        allow_all:
                            handler: bearer_static_token
                            handler_settings:
                                secret_token: 'secret-token'
                                as_user: 'admin'
                            allowed_commands: []  # list of allowed commands
                            denied_commands: []  # list of denied commands
        """

    __password_lobby_yaml__ = """
        pyknic:
            fastapi:
                lobby:
                    aaa_policies:
                        allow_all:
                            handler: inline_htpasswd
                            handler_settings:
                                credentials:
                                    - 'foo:$2y$05$Z7/3diNsWaUZ1JtEqQRdu.78F86tPEzPn/nEBTSVVyIugQtkAyRVK'
                            allowed_commands: []  # list of allowed commands
                            denied_commands: []  # list of denied commands
        """

    @AsyncFastAPIFixture.base_config(LobbyApp, __trust_lobby_yaml__)
    @pyknic_async_test
    async def test_trust(
        self,
        module_event_loop: asyncio.AbstractEventLoop,
        fastapi_module_fixture: AsyncFastAPIFixture,
        lobby_shm_secrets: typing.Callable[[str, str], typing.Coroutine[None, None, None]]
    ) -> None:
        assert(len(LoginCommand.command_name()) > 0)  # check that there is a name
        assert(LoginCommand.command_model() is LoginCommandModel)

        lobby_path = fastapi_module_fixture.app_config["pyknic"]["fastapi"]["lobby"]["main_url_path"]
        lobby_url = f'http://localhost:8000{lobby_path}'

        lobby_cmd = LoginCommandModel(
            server=MainBellBoyCommandModel(
                lobby_url=lobby_url,
                secret_backend=SecretBackendType.shm
            ),
            authentication=AuthenticationMode.trust
        )

        result = await LoginCommand.prepare_command(lobby_cmd).exec()
        assert(isinstance(result, LobbyStrFeedbackResult))
        assert(len(result.str_result) > 0)  # check that there is a response

        lobby_cmd_w_secret = LoginCommandModel(
            server=MainBellBoyCommandModel(
                lobby_url=lobby_url,
                secret_backend=SecretBackendType.shm
            ),
            authentication=AuthenticationMode.trust,
            secret=SecretReadModel(
                direct='some-secret'
            )
        )

        with pytest.raises(ValueError):
            _ = await LoginCommand.prepare_command(lobby_cmd_w_secret).exec()

    @AsyncFastAPIFixture.base_config(LobbyApp, __token_lobby_yaml__)
    @pyknic_async_test
    async def test_token_direct(
        self,
        module_event_loop: asyncio.AbstractEventLoop,
        fastapi_module_fixture: AsyncFastAPIFixture,
        lobby_shm_secrets: typing.Callable[[str, str], typing.Coroutine[None, None, None]]
    ) -> None:

        lobby_path = fastapi_module_fixture.app_config["pyknic"]["fastapi"]["lobby"]["main_url_path"]
        lobby_url = f'http://localhost:8000{lobby_path}'

        lobby_cmd_wo_token = LoginCommandModel(
            server=MainBellBoyCommandModel(
                lobby_url=lobby_url,
                secret_backend=SecretBackendType.shm
            ),
            authentication=AuthenticationMode.token
        )

        with pytest.raises(ValueError):
            _ = await LoginCommand.prepare_command(lobby_cmd_wo_token).exec()

        lobby_cmd = LoginCommandModel(
            server=MainBellBoyCommandModel(
                lobby_url=lobby_url,
                secret_backend=SecretBackendType.shm
            ),
            authentication=AuthenticationMode.token,
            secret=SecretReadModel(
                direct='secret-token'
            )
        )

        result = await LoginCommand.prepare_command(lobby_cmd).exec()

        assert(isinstance(result, LobbyStrFeedbackResult))
        assert(len(result.str_result) > 0)  # check that there is a response

    @AsyncFastAPIFixture.base_config(LobbyApp, __token_lobby_yaml__)
    @pyknic_async_test
    async def test_token_env_var(
        self,
        monkeypatch: MonkeyPatch,
        module_event_loop: asyncio.AbstractEventLoop,
        fastapi_module_fixture: AsyncFastAPIFixture,
        lobby_shm_secrets: typing.Callable[[str, str], typing.Coroutine[None, None, None]]
    ) -> None:
        monkeypatch.setenv("TEST_LOBBY_PASS", "secret-token")

        lobby_path = fastapi_module_fixture.app_config["pyknic"]["fastapi"]["lobby"]["main_url_path"]
        lobby_url = f'http://localhost:8000{lobby_path}'

        lobby_cmd = LoginCommandModel(
            server=MainBellBoyCommandModel(
                lobby_url=lobby_url,
                secret_backend=SecretBackendType.shm
            ),
            authentication=AuthenticationMode.token,
            secret=SecretReadModel(
                **{"env-var": "TEST_LOBBY_PASS"}
            )
        )

        result = await LoginCommand.prepare_command(lobby_cmd).exec()

        assert(isinstance(result, LobbyStrFeedbackResult))
        assert(len(result.str_result) > 0)  # check that there is a response

    @AsyncFastAPIFixture.base_config(LobbyApp, __token_lobby_yaml__)
    @pyknic_async_test
    async def test_token_file(
        self,
        tmp_path: pathlib.Path,
        module_event_loop: asyncio.AbstractEventLoop,
        fastapi_module_fixture: AsyncFastAPIFixture,
        lobby_shm_secrets: typing.Callable[[str, str], typing.Coroutine[None, None, None]]
    ) -> None:

        password_file = tmp_path / "password.txt"
        with password_file.open(mode="w") as f:
            f.write("secret-token")

        lobby_path = fastapi_module_fixture.app_config["pyknic"]["fastapi"]["lobby"]["main_url_path"]
        lobby_url = f'http://localhost:8000{lobby_path}'

        lobby_cmd = LoginCommandModel(
            server=MainBellBoyCommandModel(
                lobby_url=lobby_url,
                secret_backend=SecretBackendType.shm
            ),
            authentication=AuthenticationMode.token,
            secret=SecretReadModel(
                file=str(password_file)
            )
        )

        result = await LoginCommand.prepare_command(lobby_cmd).exec()

        assert(isinstance(result, LobbyStrFeedbackResult))
        assert(len(result.str_result) > 0)  # check that there is a response

    @AsyncFastAPIFixture.base_config(LobbyApp, __password_lobby_yaml__)
    @pyknic_async_test
    async def test_password(
        self,
        module_event_loop: asyncio.AbstractEventLoop,
        fastapi_module_fixture: AsyncFastAPIFixture,
        lobby_shm_secrets: typing.Callable[[str, str], typing.Coroutine[None, None, None]]
    ) -> None:

        lobby_path = fastapi_module_fixture.app_config["pyknic"]["fastapi"]["lobby"]["main_url_path"]
        lobby_url = f'http://localhost:8000{lobby_path}'

        lobby_cmd_wo_login = LoginCommandModel(
            server=MainBellBoyCommandModel(
                lobby_url=lobby_url,
                secret_backend=SecretBackendType.shm
            ),
            authentication=AuthenticationMode.basic,
            secret=SecretReadModel(
                direct='bar'
            )
        )

        with pytest.raises(ValueError):
            _ = await LoginCommand.prepare_command(lobby_cmd_wo_login).exec()

        lobby_cmd = LoginCommandModel(
            server=MainBellBoyCommandModel(
                lobby_url=lobby_url,
                secret_backend=SecretBackendType.shm
            ),
            authentication=AuthenticationMode.basic,
            login='foo',
            secret=SecretReadModel(
                direct='bar'
            )
        )

        result = await LoginCommand.prepare_command(lobby_cmd).exec()

        assert(isinstance(result, LobbyStrFeedbackResult))
        assert(len(result.str_result) > 0)  # check that there is a response
