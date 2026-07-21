# -*- coding: utf-8 -*-

import asyncio

from pyknic.lib.crypto.rsa import RSAPrivateKey
from pyknic.lib.integrated_commands.list_logins import ListLoginsCommand
from pyknic.lib.integrated_commands.logout import LogoutCommand
from pyknic.lib.bellboy.models import RequiredMainBellBoyCommandModel, MainBellBoyCommandModel, SecretBackendType
from pyknic.lib.bellboy.secret_backend import SecretBackend, SharedMemorySecretBackend
from pyknic.lib.fastapi.models.lobby import LobbyListValueFeedbackResult, LobbyEncodedJWT, LobbyPublicKeyModel
from pyknic.lib.bellboy.models import SecretBackendBellBoyCommandModel

from fixtures.asyncio import pyknic_async_test


class TestLogoutCommand:

    @pyknic_async_test
    async def test(
        self,
        module_event_loop: asyncio.AbstractEventLoop,
    ) -> None:
        assert(len(LogoutCommand.command_name()) > 0)  # check that there is a name
        assert(LogoutCommand.command_model() is RequiredMainBellBoyCommandModel)

        lobby_url = 'http://lobby.localhost:8080/some-test-endpoint/api'

        logout_lobby_options = RequiredMainBellBoyCommandModel(
            server=MainBellBoyCommandModel(
                lobby_url=lobby_url,
                secret_backend=SecretBackendType.shm
            )
        )
        secret_backend = SecretBackend(SharedMemorySecretBackend())
        await LogoutCommand.prepare_command(logout_lobby_options).exec()  # it is ok to logout from unknown url

        private_key = RSAPrivateKey.generate(1024)
        secret_backend.set_secret(
            lobby_url,
            LobbyPublicKeyModel(
                pem=private_key.public_key().export_pem().decode('ascii'),
                sign_hash_method='some-hash'
            ),
            LobbyEncodedJWT(token_data='some-token')
        )

        list_lobby_options = SecretBackendBellBoyCommandModel(
            secret_backend=SecretBackendType.shm
        )

        result = await ListLoginsCommand.prepare_command(list_lobby_options).exec()
        assert(isinstance(result, LobbyListValueFeedbackResult))
        assert(lobby_url in result.list_result)

        await LogoutCommand.prepare_command(logout_lobby_options).exec()  # it is ok to logout from known url also =)
