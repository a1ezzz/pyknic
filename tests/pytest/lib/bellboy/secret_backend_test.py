# -*- coding: utf-8 -*-

import os

import pytest

import keyring
import keyring.backends.fail
import keyring.errors

from pyknic.lib.bellboy.secret_backend import PyknicLobbySecrets, SecretBackendImplementationProto, SecretBackend
from pyknic.lib.bellboy.secret_backend import KeyringSecretBackendImplementation, SharedMemorySecretBackend
from pyknic.lib.crypto.rsa import RSAPrivateKey
from pyknic.lib.fastapi.models.lobby import LobbyEncodedJWT, LobbyPublicKeyModel


def test_abstract() -> None:
    pytest.raises(TypeError, SecretBackendImplementationProto)
    pytest.raises(
        NotImplementedError, SecretBackendImplementationProto.receive_secrets, None
    )  # type: ignore[call-overload]
    pytest.raises(
        NotImplementedError, SecretBackendImplementationProto.save_secrets, None, ''
    )  # type: ignore[call-overload]


class TestSecretBackend:

    @pytest.mark.skipif('DBUS_SESSION_BUS_ADDRESS' not in os.environ, reason='no keyring backend available')
    def test_detect_dbus_first(self) -> None:
        backend = SecretBackend.detect_backend()
        assert(isinstance(backend, KeyringSecretBackendImplementation))

    def test_detect_shm(self) -> None:
        current_keyring = keyring.get_keyring()
        try:
            # forces keyring to become disabled
            keyring.set_keyring(keyring.backends.fail.Keyring())  # type: ignore[no-untyped-call]

            backend = SecretBackend.detect_backend()
            assert(isinstance(backend, SharedMemorySecretBackend))
        finally:
            # reinitialize keyring
            keyring.set_keyring(current_keyring)

    @pytest.mark.parametrize('backend, enable_test', [
        [KeyringSecretBackendImplementation(), 'DBUS_SESSION_BUS_ADDRESS' in os.environ],
        [SharedMemorySecretBackend(), True]
    ])
    def test_backend(self, backend: SecretBackendImplementationProto, enable_test: bool) -> None:
        if not enable_test:
            return

        localhost_secret = LobbyEncodedJWT(token_data='foo-bar')
        some_host_secret = LobbyEncodedJWT(token_data='bar-foo')
        private_key = RSAPrivateKey.generate(1024)
        public_key_pem = private_key.public_key().export_pem().decode('ascii')

        storage = SecretBackend(backend)
        storage.purge()
        storage.set_secret(
            'http://localhost/',
            LobbyPublicKeyModel(
                pem=private_key.public_key().export_pem().decode('ascii'),
                sign_hash_method='some-hash-method'
            ),
            localhost_secret
        )
        storage.set_secret(
            'http://somehost/',
            LobbyPublicKeyModel(
                pem=private_key.public_key().export_pem().decode('ascii'),
                sign_hash_method='some-hash-method'
            ),
            some_host_secret
        )

        secrets = storage.get_secrets()
        assert(isinstance(secrets, PyknicLobbySecrets))
        assert(len(secrets.secrets.keys()) == 2)

        assert(secrets.secrets['http://localhost/'].jwt_token == localhost_secret)
        assert(secrets.secrets['http://localhost/'].public_key.pem == public_key_pem)
        assert(secrets.secrets['http://somehost/'].jwt_token == some_host_secret)
        assert(secrets.secrets['http://somehost/'].public_key.pem == public_key_pem)

        storage.pop_secret('http://somehost/')
        secrets = storage.get_secrets()
        assert(len(secrets.secrets.keys()) == 1)
        assert(secrets.secrets['http://localhost/'].jwt_token == localhost_secret)

    @pytest.mark.parametrize('backend, enable_test', [
        [KeyringSecretBackendImplementation(), 'DBUS_SESSION_BUS_ADDRESS' in os.environ],
        [SharedMemorySecretBackend(), True]
    ])
    def test_corrupted_backend(self, backend: SecretBackendImplementationProto, enable_test: bool) -> None:
        if not enable_test:
            return

        invalid_data = '???'
        backend.save_secrets(invalid_data)

        storage = SecretBackend(backend)
        secrets = storage.get_secrets()
        assert(len(secrets.secrets.keys()) == 0)
