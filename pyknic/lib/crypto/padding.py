# -*- coding: utf-8 -*-
# pyknic/lib/crypto/padding.py
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

from pyknic.lib.io import IOGenerator
from pyknic.lib.crypto.proto import BlockPaddingProto
from pyknic.lib.verify import verify_value
from pyknic.lib.crypto.random import random_int
from pyknic.lib.io.aligner import Aligner


class SimplePadding(BlockPaddingProto):
    """ Class that pads given data with specified ASCII character
    """

    @verify_value(padding=lambda x: x is None or len(x) == 1)
    def __init__(self, padding: typing.Optional[bytes] = None, always_pad: bool = False):
        """ Create new padding class

        :param padding: integer code of ASCII character
        :param always_pad: whether a data should be always padded
        """
        BlockPaddingProto.__init__(self)

        if padding is None:
            padding = bytes([0])
        self.__padding_symbol = padding
        self.__always_pad = always_pad

        self.__processed_bytes = 0

    def padding_symbol(self) -> bytes:
        """ Return character with witch data is padded

        :return: bytes
        """
        return self.__padding_symbol

    def always_pad(self) -> bool:
        """Return True if padding will always be made event it is aligned already
        """
        return self.__always_pad

    @verify_value(block_size=lambda x: x > 0)
    def pad(self, data: IOGenerator, block_size: int) -> IOGenerator:
        """ :meth:`.BlockPaddingProto.pad` method implementation
        """

        if self.__processed_bytes != 0:
            raise RuntimeError('The "pad" or the "undo_pad" method has already been called')

        for i in data:
            self.__processed_bytes += len(i)
            yield i

        pad_length = block_size - (self.__processed_bytes % block_size)
        if pad_length == block_size and not self.__always_pad:
            pad_length = 0

        yield self.padding_symbol() * pad_length

    @verify_value(block_size=lambda x: x > 0)
    def undo_pad(self, data: IOGenerator, block_size: int) -> IOGenerator:
        """ :meth:`.BlockPaddingProto.undo_pad` method implementation
        """

        if self.__processed_bytes != 0:
            raise RuntimeError('The "pad" or the "undo_pad" method has already been called')

        aligner = Aligner(block_size, strict_mode=True)

        prev_block, next_block = None, None
        for aligner_block in aligner.iterate_data(data):
            if prev_block is not None:
                yield prev_block

            prev_block, next_block = next_block, aligner_block

        if prev_block is not None:
            yield prev_block

        if next_block is None:
            raise RuntimeError('There is no data. It seams that this data was not padded')

        if self.__always_pad and not next_block.endswith(self.padding_symbol()):
            raise RuntimeError('Invalid last symbol. It seams that this data was not padded')

        yield next_block.rstrip(self.padding_symbol())


class ZeroPadding(SimplePadding):
    """ Zero padding implementation (just alias for SimplePadding object)

    see also: https://en.wikipedia.org/wiki/Padding_(cryptography)#Zero_padding
    """

    def __init__(self) -> None:
        """ Create new padding object
        """
        SimplePadding.__init__(self, always_pad=True)


class ShiftPadding(SimplePadding):
    """ Same as :class:`.SimplePadding` class, but also randomly shifts original data.
    """

    def __init__(self, padding: typing.Optional[bytes] = None) -> None:
        """Create new padding object

        :param padding: same as the "padding" parameter in the :meth:`.SimplePadding.__init__` method
        """
        SimplePadding.__init__(self, padding=padding, always_pad=True)

    @verify_value(block_size=lambda x: x > 0)
    def pad(self, data: IOGenerator, block_size: int) -> IOGenerator:
        """ :meth:`.BlockPaddingProto.pad` method implementation
        """

        def shifted_data(original_data: IOGenerator) -> IOGenerator:

            shift_length = random_int(block_size)
            if shift_length == 0:
                shift_length = 1

            yield self.padding_symbol() * shift_length

            for i in original_data:
                yield i

        return SimplePadding.pad(self, shifted_data(data), block_size)

    @verify_value(block_size=lambda x: x > 0)
    def undo_pad(self, data: IOGenerator, block_size: int) -> IOGenerator:
        """ :meth:`.BlockPaddingProto.undo_pad` method implementation
        """

        first_chunk: typing.Optional[bytes] = b''
        for i in SimplePadding.undo_pad(self, data, block_size):
            if first_chunk is None:
                yield i
                continue

            first_chunk += i
            first_chunk = first_chunk.lstrip(self.padding_symbol())
            if len(first_chunk):
                yield first_chunk
                first_chunk = None


class PKCS7Padding(BlockPaddingProto):
    """ PKCS7 Padding implementation

    see also: https://en.wikipedia.org/wiki/Padding_(cryptography)#PKCS7
    """

    def __init__(self) -> None:
        """ Create new padding class
        """
        BlockPaddingProto.__init__(self)
        self.__processed_bytes = 0

    @verify_value(block_size=lambda x: x > 0)
    def pad(self, data: IOGenerator, block_size: int) -> IOGenerator:
        """ :meth:`.BlockPaddingProto.pad` method implementation
        """

        if block_size >= 256:
            raise RuntimeError('The PKCS7 padding method is not supported for block size >= 256')

        if self.__processed_bytes != 0:
            raise RuntimeError('The "pad" or the "undo_pad" method has already been called')

        for i in data:
            self.__processed_bytes += len(i)
            yield i

        pad_length = block_size - (self.__processed_bytes % block_size)
        yield bytes([pad_length] * pad_length)

    @verify_value(block_size=lambda x: x > 0)
    def undo_pad(self, data: IOGenerator, block_size: int) -> IOGenerator:
        """ :meth:`.BlockPaddingProto.undo_pad` method implementation
        """

        if block_size >= 256:
            raise RuntimeError('The PKCS7 padding method is not supported for block size >= 256')

        if self.__processed_bytes != 0:
            raise RuntimeError('The "pad" or the "undo_pad" method has already been called')

        aligner = Aligner(block_size, strict_mode=True)

        prev_block, next_block = None, None
        for aligner_block in aligner.iterate_data(data):
            if prev_block is not None:
                yield prev_block

            prev_block, next_block = next_block, aligner_block

        if prev_block is not None:
            yield prev_block

        if next_block is None:
            raise RuntimeError('There is no data. It seams that this data was not padded')

        padded = next_block[-1]
        if padded == 0 or padded > block_size:
            raise RuntimeError('Invalid last byte. It seams that this data was not padded with PKCS7')

        yield next_block[:-padded]
