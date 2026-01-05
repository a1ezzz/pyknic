# -*- coding: utf-8 -*-
# pyknic/lib/io/crypto/proto.py
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

from pyknic.lib.io import IOGenerator
from pyknic.lib.verify import verify_value


class CipherProto(metaclass=ABCMeta):
    """ This class is a generalization of ciphers (now it is AES cipher only)
    """

    @abstractmethod
    def block_size(self) -> typing.Optional[int]:
        """Return a size of a block that may be encrypted or decrypted.

        :return: int (in bytes) or None if cipher is able to encrypt/decrypt block with any length
        """
        raise NotImplementedError('This method is abstract')

    @abstractmethod
    def encrypt(self, data: IOGenerator) -> IOGenerator:
        """ Encrypt the given data

        :param data: data to encrypt. The size of the data must be multiple of :meth:`.CipherProto.block_size`
        """
        raise NotImplementedError('This method is abstract')

    @abstractmethod
    def decrypt(self, data: IOGenerator) -> IOGenerator:
        """ Decrypt the given data

        :param data: data to decrypt. The size of the data must be multiple of :meth:`.CipherProto.block_size`

        :return: bytes
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
