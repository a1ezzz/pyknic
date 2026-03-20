# -*- coding: utf-8 -*-

import os

import pytest

import keyring
import keyring.backends.fail
import keyring.errors

from pyknic.lib.bellboy.secret_backend import PyknicLobbySecrets, SecretBackendImplementationProto, SecretBackend
from pyknic.lib.bellboy.secret_backend import KeyringSecretBackendImplementation, SharedMemorySecretBackend
from pyknic.lib.fastapi.lobby_fingerprint import LobbyFingerprint


def test_abstract() -> None:
    pytest.raises(TypeError, SecretBackendImplementationProto)
    pytest.raises(NotImplementedError, SecretBackendImplementationProto.receive_secrets, None)
    pytest.raises(NotImplementedError, SecretBackendImplementationProto.save_secrets, None, '')


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

        localhost_secret = 'foo-bar'
        some_host_secret = 'bar-foo'
        fingerprint = LobbyFingerprint.generate_fingerprint()

        storage = SecretBackend(backend)
        storage.purge()
        storage.set_secret('http://localhost/', fingerprint, localhost_secret)
        storage.set_secret('http://somehost/', fingerprint, some_host_secret)

        secrets = storage.get_secrets()
        assert(isinstance(secrets, PyknicLobbySecrets))
        assert(len(secrets.secrets.keys()) == 2)

        assert(secrets.secrets['http://localhost/'].token == localhost_secret)
        assert(secrets.secrets['http://localhost/'].server_fingerprint.fingerprint == str(fingerprint))
        assert(secrets.secrets['http://somehost/'].token == some_host_secret)
        assert(secrets.secrets['http://somehost/'].server_fingerprint.fingerprint == str(fingerprint))

        storage.pop_secret('http://somehost/')
        secrets = storage.get_secrets()
        assert(len(secrets.secrets.keys()) == 1)
        assert(secrets.secrets['http://localhost/'].token == localhost_secret)

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
