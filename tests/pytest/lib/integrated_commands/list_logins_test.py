# -*- coding: utf-8 -*-

import asyncio

from pyknic.lib.integrated_commands.list_logins import ListLoginsCommand
from pyknic.lib.bellboy.models import SecretBackendBellBoyCommandModel, SecretBackendType
from pyknic.lib.bellboy.secret_backend import SecretBackend, SharedMemorySecretBackend
from pyknic.lib.fastapi.lobby_fingerprint import LobbyFingerprint
from pyknic.lib.fastapi.models.lobby import LobbyListValueFeedbackResult

from fixtures.asyncio import pyknic_async_test


class TestListLoginsCommand:

    @pyknic_async_test
    async def test(
        self,
        module_event_loop: asyncio.AbstractEventLoop,
    ) -> None:
        assert(len(ListLoginsCommand.command_name()) > 0)  # check that there is a name
        assert(ListLoginsCommand.command_model() is SecretBackendBellBoyCommandModel)

        lobby_options = SecretBackendBellBoyCommandModel(
            secret_backend=SecretBackendType.shm
        )
        secret_backend = SecretBackend(SharedMemorySecretBackend())

        result = await ListLoginsCommand.exec(args=lobby_options)
        assert(isinstance(result, LobbyListValueFeedbackResult))

        lobby_url = 'http://lobby.localhost:8080/some-test-endpoint/api'
        secret_backend.set_secret(lobby_url, LobbyFingerprint.generate_fingerprint(), 'some-token')

        result = await ListLoginsCommand.exec(args=lobby_options)
        assert(isinstance(result, LobbyListValueFeedbackResult))
        assert(lobby_url in result.list_result)
