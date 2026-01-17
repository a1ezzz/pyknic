# -*- coding: utf-8 -*-
# pyknic/lib/crypto/proto.py
#
# Copyright (C) 2018-2026 the pyknic authors and contributors
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

import typing

from abc import ABCMeta, abstractmethod

from cryptography.hazmat.primitives.hashes import HashAlgorithm as C10yHashAlgorithm

from pyknic.lib.io import IOGenerator
from pyknic.lib.verify import verify_value


class HasherProto(metaclass=ABCMeta):
    """This is a base class for all generalized hashers."""

    @abstractmethod
    def update(self, source: IOGenerator) -> IOGenerator:
        """Update digest and yield all the received data.

        :param source: a data to update digest
        """
        raise NotImplementedError('This method is abstract')

    @abstractmethod
    def digest(self) -> bytes:
        """Return generated digest."""
        raise NotImplementedError('This method is abstract')

    @abstractmethod
    def c10y_algorithm(self) -> typing.Optional[C10yHashAlgorithm]:
        """If available -- return object of the "cryptography" module which implements the hash algorithm
        """
        return None


class CipherProto(metaclass=ABCMeta):
    """ This class is a generalization of ciphers (now it is AES cipher only)
    """

    @classmethod
    @abstractmethod
    def algo_block_size(cls) -> typing.Optional[int]:
        """Return cipher's block size

        :return: int (in bytes) or None if cipher is a stream cipher (not a block cipher)
        """
        raise NotImplementedError('This method is abstract')

    @classmethod
    @abstractmethod
    def key_size(cls) -> typing.Optional[int]:
        """Return a size of a key this cipher require

        :return: int (in bytes) or None if cipher is able to use a key with any length
        """
        raise NotImplementedError('This method is abstract')

    @classmethod
    @abstractmethod
    def create_encryptor(cls, key: bytes) -> 'CipherProto':
        """Create a new cipher object that is able to encrypt data (decryption may not be possible and
        calling to the :meth:`.CipherProto.decrypt` should be avoided)

        :param key: key to use for encryption
        """

        raise NotImplementedError('This method is abstract')

    @classmethod
    @abstractmethod
    def create_decryptor(cls, key: bytes, decryptor_init_data: typing.Any) -> 'CipherProto':
        """Create a new cipher object that is able to decrypt data (encryption may not be possible and
        calling to the :meth:`.CipherProto.encrypt` should be avoided)

        :param key: key to use for decryption
        :param decryptor_init_data: initialization data with which cipher was created.
        See the :meth:`.CipherProto.decryptor_init_data` method
        """

        raise NotImplementedError('This method is abstract')

    @abstractmethod
    def decryptor_init_data(self) -> typing.Any:
        """Initialization data with which this cipher was created. This data may contain some random bytes (like nonce
        or initialization vector) that are crucial for decryption. This data is safe to transmit along with secured
        message.

        :note: result of this method should be able to serialize to JSON
        """
        raise NotImplementedError('This method is abstract')

    @abstractmethod
    def encrypt(self, data: IOGenerator) -> IOGenerator:
        """Encrypt the given data

        :param data: data to encrypt
        """
        raise NotImplementedError('This method is abstract')

    @abstractmethod
    def decrypt(self, data: IOGenerator) -> IOGenerator:
        """Decrypt the given data

        :param data: data to decrypt
        """
        raise NotImplementedError('This method is abstract')


class BlockPaddingProto(metaclass=ABCMeta):
    """ Padding/reverse padding class prototype
    """

    @abstractmethod
    @verify_value(block_size=lambda x: x > 0)
    def pad(self, data: IOGenerator, block_size: int) -> IOGenerator:
        """ Pad given data to given size

        :param data: data to pad
        :param block_size: size to pad
        :return: bytes
        """
        raise NotImplementedError("This method is abstract")

    @abstractmethod
    @verify_value(block_size=lambda x: x > 0)
    def undo_pad(self, data: IOGenerator, block_size: int) -> IOGenerator:
        """Remove pads and return original data

        :param data: data to remove pads from
        :param block_size: size data aligned to
        :return: bytes
        """
        raise NotImplementedError("This method is abstract")
