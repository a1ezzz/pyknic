# -*- coding: utf-8 -*-

import asyncio

from pyknic.lib.integrated_commands.list_logins import ListLoginsCommand
from pyknic.lib.integrated_commands.logout import LogoutCommand
from pyknic.lib.bellboy.models import GeneralBellBoyCommandModel, SecretBackendType
from pyknic.lib.bellboy.secret_backend import SecretBackend, SharedMemorySecretBackend
from pyknic.lib.fastapi.lobby_fingerprint import LobbyFingerprint
from pyknic.lib.fastapi.models.lobby import LobbyListValueFeedbackResult

from fixtures.asyncio import pyknic_async_test


class TestLogoutCommand:

    @pyknic_async_test
    async def test(
        self,
        module_event_loop: asyncio.AbstractEventLoop,
    ) -> None:
        assert(len(LogoutCommand.command_name()) > 0)  # check that there is a name
        assert(LogoutCommand.command_model() is GeneralBellBoyCommandModel)

        lobby_url = 'http://lobby.localhost:8080/some-test-endpoint/api'

        lobby_options = GeneralBellBoyCommandModel(
            lobby_url=lobby_url,
            secret_backend=SecretBackendType.shm
        )
        secret_backend = SecretBackend(SharedMemorySecretBackend())

        await LogoutCommand.prepare_command(lobby_options).exec()  # it is ok to logout from unknown url

        secret_backend.set_secret(lobby_url, LobbyFingerprint.generate_fingerprint(), 'some-token')
        result = await ListLoginsCommand.prepare_command(lobby_options).exec()
        assert(isinstance(result, LobbyListValueFeedbackResult))
        assert(lobby_url in result.list_result)

        await LogoutCommand.prepare_command(lobby_options).exec()  # it is ok to logout from known url also =)
