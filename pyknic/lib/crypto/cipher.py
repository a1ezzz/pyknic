# -*- coding: utf-8 -*-
# pyknic/lib/io/crypto/cipher.py
#
# Copyright (C) 2016-2026 the pyknic authors and contributors
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
import typing

from abc import abstractmethod

import pydantic

from cryptography.hazmat.primitives.ciphers import Cipher, modes
from cryptography.hazmat.primitives.ciphers.algorithms import AES as C10yAES
from cryptography.hazmat.backends import default_backend

from pyknic.lib.io import IOGenerator
from pyknic.lib.io.aligner import Aligner
from pyknic.lib.registry import APIRegistry, register_api
from pyknic.lib.crypto.random import random_bytes
from pyknic.lib.crypto.proto import CipherProto

# TODO: review modern security recommendations periodically --
#  https://cryptography.io/en/latest/hazmat/primitives/symmetric-encryption/

__default_cipher_registry__ = APIRegistry()


class CipherModeModel(pydantic.BaseModel):
    """This base model helps to describe data that requires for cipher mode initialization.
    """

    @classmethod
    def generate(cls, cipher: CipherProto) -> 'CipherModeModel':
        """Create a cipher mode initialized with random data

        :param cipher: Cipher which will be used with this mode
        """
        raise NotImplementedError('This method is abstract')

    @classmethod
    def deserialize(cls, model_data: typing.Dict[str, typing.Any], cipher: CipherProto) -> 'CipherModeModel':
        """Import dumped models (python dictionary) into this model

        :param model_data: dumped model data
        :param cipher: cipher which will be used with this mode
        """
        raise NotImplementedError('This method is abstract')

    def c10y_mode(self) -> modes.Mode:
        """Create object suitable to use with the "cryptography" package
        """
        raise NotImplementedError('This method is abstract')


class CBCMode(CipherModeModel):
    """The :class:`.CipherModeModel` model implementation that describes CBC-mode

    see also: https://cryptography.io/en/latest/hazmat/primitives/symmetric-encryption/#cryptography.hazmat.primitives.ciphers.modes.CBC  # noqa: E501
    """

    initialization_vector: pydantic.Base64Bytes
    mode: typing.Literal['CBC'] = pydantic.Field(default='CBC', frozen=True)

    @classmethod
    def generate(cls, cipher: CipherProto) -> 'CBCMode':
        """The :meth:`.CipherModeModel.generate` method implementation
        """
        block_size = cipher.algo_block_size()
        assert(block_size is not None)
        return CBCMode(initialization_vector=base64.b64encode(random_bytes(block_size)))

    @classmethod
    def deserialize(cls, model_data: typing.Dict[str, typing.Any], cipher: CipherProto) -> 'CBCMode':
        """The :meth:`.CipherModeModel.deserialize` method implementation
        """
        mode = CBCMode.model_validate(model_data)
        if len(mode.initialization_vector) != cipher.algo_block_size():
            raise ValueError("Invalid initialization vector length")
        return mode

    def c10y_mode(self) -> modes.Mode:
        """The :meth:`.CipherModeModel.c10y_mode` method implementation
        """
        return modes.CBC(self.initialization_vector)


class CTRMode(CipherModeModel):
    """The :class:`.CipherModeModel` model implementation that describes CBC-mode

    see also: https://cryptography.io/en/latest/hazmat/primitives/symmetric-encryption/#cryptography.hazmat.primitives.ciphers.modes.CTR  # noqa: E501

    :note: please note minimal block size!
    """

    nonce: pydantic.Base64Bytes = pydantic.Field(min_length=22)  # (((128 / 8) / 3) * 4) -- length of base64-encoded
    # string required for 128-bit block
    mode: typing.Literal['CTR'] = pydantic.Field(default='CTR', frozen=True)

    @classmethod
    def generate(cls, cipher: CipherProto) -> 'CTRMode':
        """The :meth:`.CipherModeModel.generate` method implementation
        """
        block_size = cipher.algo_block_size()
        assert(block_size is not None)
        return CTRMode(nonce=base64.b64encode(random_bytes(block_size)))

    @classmethod
    def deserialize(cls, model_data: typing.Dict[str, typing.Any], cipher: CipherProto) -> 'CTRMode':
        """The :meth:`.CipherModeModel.deserialize` method implementation
        """
        mode = CTRMode.model_validate(model_data)
        if len(mode.nonce) != cipher.algo_block_size():
            raise ValueError("Invalid nonce size")

        return mode

    def c10y_mode(self) -> modes.Mode:
        """The :meth:`.CipherModeModel.c10y_mode` method implementation
        """
        return modes.CTR(self.nonce)


class _PlainAESCipher(CipherProto):
    """Base class for AES implementation (without key size and without cipher mode)
    """

    @classmethod
    @abstractmethod
    def cipher_mode_model_cls(cls) -> typing.Type[CipherModeModel]:
        """Return model class for cipher mode
        """
        raise NotImplementedError('This method is abstract')

    @classmethod
    def create_encryptor(cls, key: bytes) -> 'CipherProto':
        """The :meth:`.CipherProto.create_encryptor` method implementation
        """
        return cls(key)

    @classmethod
    def create_decryptor(cls, key: bytes, decryptor_init_data: typing.Any) -> 'CipherProto':
        """The :meth:`.CipherProto.create_decryptor` method implementation
        """
        return cls(key, decryptor_init_data)

    @classmethod
    def algo_block_size(cls) -> int:
        """The :meth:`.CipherProto.algo_block_size` method implementation
        """
        return int(128 / 8)

    def __init__(self, key: bytes, init_data: typing.Any = None):
        """Create new encryptor/decryptor

        :param key: key to use
        :param init_data: decryptor's initialization data. If it is None, then this object allows encryption and
        allows decryption otherwise
        """
        CipherProto.__init__(self)

        if len(key) != self.key_size():
            raise ValueError(f"Invalid key size. It must be {self.key_size()} bytes")

        self.__key = key

        m_cls = self.cipher_mode_model_cls()
        self.__mode_model = m_cls.deserialize(init_data, self) if init_data is not None else m_cls.generate(self)
        self.__encryption_mode = init_data is None

        self.__aes_algorithm = C10yAES(key)
        self.__aes_cipher = Cipher(
            self.__aes_algorithm,
            self.__mode_model.c10y_mode(),
            backend=default_backend()
        )

    def decryptor_init_data(self) -> typing.Any:
        """The :meth:`.CipherProto.decryptor_init_data` method implementation
        """
        return self.__mode_model.model_dump()

    def encrypt(self, data: IOGenerator) -> IOGenerator:
        """The :meth:`.CipherProto.encrypt` method implementation
        """
        if not self.__encryption_mode:
            raise RuntimeError('Unable to encrypt with decryptor')

        encryptor = self.__aes_cipher.encryptor()  # type: ignore[misc]  # mypy issue
        aligner = Aligner(self.algo_block_size(), strict_mode=True)

        for i in aligner.iterate_data(data):
            yield encryptor.update(i)

        yield encryptor.finalize()

    def decrypt(self, data: IOGenerator) -> IOGenerator:
        """The :meth:`.CipherProto.decrypt` method implementation
        """

        if self.__encryption_mode:
            raise RuntimeError('Unable to decrypt with encryptor')

        decryptor = self.__aes_cipher.decryptor()  # type: ignore[misc]  # mypy issue
        aligner = Aligner(self.algo_block_size(), strict_mode=True)

        for i in aligner.iterate_data(data):
            yield decryptor.update(i)

        yield decryptor.finalize()


def _aes_ciphers_generator(
    key_size: int, model_cls: typing.Type[CipherModeModel]
) -> typing.Callable[[typing.Type[_PlainAESCipher]], typing.Type[_PlainAESCipher]]:
    """This function helps to describe specific AES ciphers

    :param key_size: The size of the key to use
    :param model_cls: The cipher mode to use
    """

    def class_decorator(origin_cls: typing.Type[_PlainAESCipher]) -> typing.Type[_PlainAESCipher]:

        class DecoratedClass(origin_cls):  # type: ignore[valid-type, misc]

            @classmethod
            def key_size(cls) -> int:
                return key_size

            @classmethod
            def cipher_mode_model_cls(cls) -> typing.Type[CipherModeModel]:
                return model_cls

        return DecoratedClass

    return class_decorator


# noinspection PyAbstractClass
@register_api(__default_cipher_registry__, 'AES-128-CBC')
@_aes_ciphers_generator(int(128 / 8), CBCMode)
class AES128CBCCipher(_PlainAESCipher):
    """The AES-128-CBC cipher implementation
    """
    pass


# noinspection PyAbstractClass
@register_api(__default_cipher_registry__, 'AES-192-CBC')
@_aes_ciphers_generator(int(192 / 8), CBCMode)
class AES192CBCCipher(_PlainAESCipher):
    """The AES-192-CBC cipher implementation
    """
    pass


# noinspection PyAbstractClass
@register_api(__default_cipher_registry__, 'AES-256-CBC')
@_aes_ciphers_generator(int(256 / 8), CBCMode)
class AES256CBCCipher(_PlainAESCipher):
    """The AES-256-CBC cipher implementation
    """
    pass


# noinspection PyAbstractClass
@register_api(__default_cipher_registry__, 'AES-128-CTR')
@_aes_ciphers_generator(int(128 / 8), CTRMode)
class AES128CTRCipher(_PlainAESCipher):
    """The AES-128-CTR cipher implementation
    """
    pass


# noinspection PyAbstractClass
@register_api(__default_cipher_registry__, 'AES-192-CTR')
@_aes_ciphers_generator(int(192 / 8), CTRMode)
class AES192CTRCipher(_PlainAESCipher):
    """The AES-192-CTR cipher implementation
    """
    pass


# noinspection PyAbstractClass
@register_api(__default_cipher_registry__, 'AES-256-CTR')
@_aes_ciphers_generator(int(256 / 8), CTRMode)
class AES256CTRCipher(_PlainAESCipher):
    """The AES-256-CTR cipher implementation
    """
    pass
