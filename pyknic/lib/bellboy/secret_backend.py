# -*- coding: utf-8 -*-
# pyknic/lib/bellboy/secret_backend.py
#
# Copyright (C) 2026 the pyknic authors and contributors
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

import abc
import contextlib
import multiprocessing.shared_memory
import sys
import typing

import keyring
import keyring.errors
import pydantic

from pyknic.lib.fastapi.lobby_fingerprint import LobbyFingerprint
from pyknic.lib.fastapi.models.lobby import LobbyFingerprintModel


class SecretTokenModel(pydantic.BaseModel):
    """This model describes a single credential that is required for a single server connection
    """
    server_fingerprint: LobbyFingerprintModel  # server's fingerprint info
    token: str                                 # server's token  # TODO: better make it with a session key!


class PyknicLobbySecrets(pydantic.BaseModel):
    """This model describes a collection of secrets
    """
    secrets: typing.Dict[str, SecretTokenModel]  # key-value, where a key is a URL of a server to which secret is saved


class SecretBackendImplementationProto(metaclass=abc.ABCMeta):
    """Prototype for secret storage that holds data
    """

    @abc.abstractmethod
    def receive_secrets(self) -> typing.Optional[str]:
        """Return from a storage a json-string, that may be parsed as the :class:`PyknicLobbySecrets` object
        """
        raise NotImplementedError('This method is abstract')

    @abc.abstractmethod
    def save_secrets(self, secrets_json_txt: str) -> None:
        """Save to a storage a json-string, that may be parsed as the :class:`PyknicLobbySecrets` object

        :param secrets_json_txt: secrets to save
        """
        raise NotImplementedError('This method is abstract')


class SecretBackend:
    """Basic implementation for a saving/loading login information.

    :note: this implementation is not concurrent safe, so be sure that you don't run tests/multiple login requests
    at the same time

    # TODO: think of a global lock that may be shared by independent processes
    """

    def __init__(self, backend_implementation: typing.Optional[SecretBackendImplementationProto] = None) -> None:
        """Create a new backend

        :param backend_implementation: backend to use. If no backend is specified, then it will be detected with
        the :meth:`.SecretBackend.detect_backend` method
        """
        self.__backend = backend_implementation if backend_implementation else SecretBackend.detect_backend()

    def get_secrets(self) -> PyknicLobbySecrets:
        """Get the secrets stored in backend"""
        try:
            secrets = self.__backend.receive_secrets()
            if secrets:
                return PyknicLobbySecrets.model_validate_json(secrets)
        except pydantic.ValidationError:
            pass

        return PyknicLobbySecrets(secrets=dict())

    def set_secret(self, url: str, fingerprint: LobbyFingerprint, token: str) -> None:
        """Save secrets in backend.
        """
        secrets = self.get_secrets()
        secrets.secrets[url] = SecretTokenModel(
            server_fingerprint=LobbyFingerprintModel(fingerprint=str(fingerprint)),
            token=token
        )
        self.__backend.save_secrets(secrets.model_dump_json())

    def pop_secret(self, url: str) -> SecretTokenModel:
        secrets = self.get_secrets()
        secret_data = secrets.secrets.pop(url)
        self.__backend.save_secrets(secrets.model_dump_json())
        return secret_data

    def purge(self) -> None:
        """Remove every secret from backend.
        """
        self.__backend.save_secrets(PyknicLobbySecrets(secrets=dict()).model_dump_json())

    @staticmethod
    def detect_backend() -> SecretBackendImplementationProto:
        """Try to find usable backend
        """
        try:
            keytool = KeyringSecretBackendImplementation()
            keytool.receive_secrets()
            return keytool
        except keyring.errors.NoKeyringError:
            return SharedMemorySecretBackend()


class KeyringSecretBackendImplementation(SecretBackendImplementationProto):
    """Keyring backend -- https://github.com/jaraco/keyring
    """

    __keytool_service__ = 'pyknic'
    __keytool_login__ = 'secrets'

    def receive_secrets(self) -> typing.Optional[str]:
        """The :meth:`.SecretBackendImplementationProto.receive_secrets` method implementation
        """
        return keyring.get_password(self.__keytool_service__, self.__keytool_login__)

    def save_secrets(self, secrets_json_txt: str) -> None:
        """The :meth:`.SecretBackendImplementationProto.save_secrets` method implementation
        """
        keyring.set_password(self.__keytool_service__, self.__keytool_login__, secrets_json_txt)


class SharedMemorySecretBackend(SecretBackendImplementationProto):
    """Shared memory backend -- look for the files in the /dev/shm directory.
    """

    __shm_filename__ = '/pyknic-secrets'  # the '/' at the beginning is crucial

    def __shared_memory_args(self) -> typing.Dict[str, typing.Any]:
        """ This is a crutch for older python versions defines extra arguments for the
        multiprocessing.shared_memory.SharedMemory constructor.
        """
        if sys.version_info >= (3, 13, 0):
            return {'track': False}
        return {}

    def receive_secrets(self) -> typing.Optional[str]:
        """The :meth:`.SecretBackendImplementationProto.receive_secrets` method implementation
        """
        with contextlib.suppress(FileNotFoundError):
            secret = multiprocessing.shared_memory.SharedMemory(
                self.__shm_filename__, create=False, **self.__shared_memory_args()
            )
            secret_bytes = bytes(secret.buf)
            result = secret_bytes.decode()
            secret.close()
            return result

        return None

    def save_secrets(self, secrets_json_txt: str) -> None:
        """The :meth:`.SecretBackendImplementationProto.save_secrets` method implementation
        """
        secret_bytes = secrets_json_txt.encode()

        with contextlib.suppress(FileNotFoundError):
            # force file to be removed!
            sh_mem = multiprocessing.shared_memory.SharedMemory(
                self.__shm_filename__, create=False, **self.__shared_memory_args()
            )
            sh_mem.unlink()
            sh_mem.close()

        sh_mem = multiprocessing.shared_memory.SharedMemory(
            self.__shm_filename__,
            size=len(secret_bytes),
            create=True,
            **self.__shared_memory_args()
        )
        sh_mem.buf[:] = secret_bytes
        sh_mem.close()
