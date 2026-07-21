# -*- coding: utf-8 -*-

import asyncio

from pyknic.lib.crypto.rsa import RSAPrivateKey
from pyknic.lib.integrated_commands.list_logins import ListLoginsCommand
from pyknic.lib.integrated_commands.logout_all import LogoutAllCommand
from pyknic.lib.bellboy.models import SecretBackendBellBoyCommandModel, SecretBackendType
from pyknic.lib.bellboy.secret_backend import SecretBackend, SharedMemorySecretBackend
from pyknic.lib.fastapi.models.lobby import LobbyListValueFeedbackResult, LobbyEncodedJWT, LobbyPublicKeyModel

from fixtures.asyncio import pyknic_async_test


class TestLogoutAllCommand:

    @pyknic_async_test
    async def test(
        self,
        module_event_loop: asyncio.AbstractEventLoop,
    ) -> None:
        assert(len(LogoutAllCommand.command_name()) > 0)  # check that there is a name
        assert(LogoutAllCommand.command_model() is SecretBackendBellBoyCommandModel)

        lobby_url = 'http://lobby.localhost:8080/some-test-endpoint/api'

        lobby_options = SecretBackendBellBoyCommandModel(
            secret_backend=SecretBackendType.shm
        )
        private_key = RSAPrivateKey.generate(1024)
        secret_backend = SecretBackend(SharedMemorySecretBackend())
        secret_backend.set_secret(
            lobby_url,
            LobbyPublicKeyModel(
                pem=private_key.public_key().export_pem().decode('ascii'),
                sign_hash_method='some-hash'
            ),
            LobbyEncodedJWT(token_data='some-token')
        )
        result = await ListLoginsCommand.prepare_command(lobby_options).exec()
        assert(isinstance(result, LobbyListValueFeedbackResult))
        assert(lobby_url in result.list_result)

        await LogoutAllCommand.prepare_command(lobby_options).exec()
        result = await ListLoginsCommand.prepare_command(lobby_options).exec()
        assert(isinstance(result, LobbyListValueFeedbackResult))
        assert(lobby_url not in result.list_result)
