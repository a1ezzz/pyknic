# -*- coding: utf-8 -*-
# pyknic/lib/io/compression.py
#
# Copyright (C) 2025 the pyknic authors and contributors
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

# TODO: Think of https://pypi.org/project/lz4/

import bz2
import gzip
import io
import lzma
import os
import typing

from abc import ABCMeta, abstractmethod

from pyknic.lib.registry import APIRegistry, register_api
from pyknic.lib.io import __default_block_size__, IOGenerator, IOProducer
from pyknic.lib.io.read_fo import ReadFileObject


__default_io_compressors_registry__ = APIRegistry()


class CompressorProto(metaclass=ABCMeta):
    """This is the base class for all compressors.
    """

    @abstractmethod
    def compress(self, source: IOProducer) -> IOGenerator:
        """Compress data and yield compressed chunks

        :param source: a data to compress
        """
        raise NotImplementedError('This method is abstract')

    @abstractmethod
    def decompress(self, source: IOProducer) -> IOGenerator:
        """Decompress data and yield uncompressed chunks

        :param source: a compressed data
        """
        raise NotImplementedError('This method is abstract')


class NativeCompressor(CompressorProto):
    """This is an adapter for CPython compressors.
    """

    @abstractmethod
    def _compressor(self, io_buffer: typing.BinaryIO, mode: str) -> io.BufferedRWPair:
        """Return object that has common compressor methods that every CPython compressor has.

        :param io_buffer: an internal buffer that compressor works with
        :param mode: a mode with which a compressor should be opened (like 'rb' or 'wb')
        """
        raise NotImplementedError('This method is abstract')

    def compress(self, source: IOProducer) -> IOGenerator:
        """The :meth:`.CompressorProto.compress` method implementation."""
        compress_buffer = io.BytesIO()
        compressor = self._compressor(compress_buffer, 'wb')

        for data in source:
            compressor.write(data)

            comp_data = compress_buffer.getvalue()
            yield comp_data

            compress_buffer.truncate(0)
            compress_buffer.seek(0, os.SEEK_SET)

        compressor.flush()
        compressor.close()

        yield compress_buffer.getvalue()

    def decompress(self, source: IOProducer) -> IOGenerator:
        """The :meth:`.CompressorProto.decompress` method implementation."""

        rfo = ReadFileObject(source)
        compressor = self._compressor(rfo, 'rb')

        chunk = compressor.read(__default_block_size__)
        while chunk:
            yield chunk
            chunk = compressor.read(__default_block_size__)


@register_api(__default_io_compressors_registry__, "gzip")
class GZipCompressor(NativeCompressor):
    """GZip implementation."""

    def _compressor(self, io_buffer: typing.BinaryIO, mode: str) -> io.BufferedRWPair:
        """The :meth:`.NativeCompressor._compressor` method implementation."""
        return gzip.GzipFile(fileobj=io_buffer, mode=mode)  # type: ignore[return-value]


@register_api(__default_io_compressors_registry__, "bzip2")
class BZip2Compressor(NativeCompressor):
    """BZip2 implementation."""

    def _compressor(self, io_buffer: typing.BinaryIO, mode: str) -> io.BufferedRWPair:
        """The :meth:`.NativeCompressor._compressor` method implementation."""
        return bz2.BZ2File(io_buffer, mode=mode)  # type: ignore[no-any-return, call-overload]


@register_api(__default_io_compressors_registry__, "lzma")
class LZMACompressor(NativeCompressor):
    """LZMA implementation."""

    def _compressor(self, io_buffer: typing.BinaryIO, mode: str) -> io.BufferedRWPair:
        """The :meth:`.NativeCompressor._compressor` method implementation."""
        return lzma.LZMAFile(io_buffer, mode=mode)  # type: ignore[return-value]
