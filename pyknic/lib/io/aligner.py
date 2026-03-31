# -*- coding: utf-8 -*-
# pyknic/lib/io/aligner.py
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

from pyknic.lib.io import IOGenerator, IOProducer
from pyknic.lib.verify import verify_value


class Aligner:
    """This class helps to chop IOGenerator into aligned blocks
    """

    def __init__(self, block_size: int, *, strict_mode: bool = False):
        """Create a new aligner

        :param block_size: size of block in bytes that yielded data should be aligned to
        :param strict_mode: whether to raise an exception when the last block was not aligned
        """
        self.__block_size = block_size
        self.__strict_mode = strict_mode

    def iterate_data(self, data: IOProducer) -> IOGenerator:
        """Chop data into blocks/chunks
        """

        data_cache = b''
        for i in data:
            data_cache += i

            if len(data_cache) < self.__block_size:
                continue

            next_cache_len = len(data_cache) % self.__block_size
            if next_cache_len == 0:
                yield data_cache
                data_cache = b''
            else:
                yield data_cache[:-next_cache_len]
                data_cache = data_cache[-next_cache_len:]

        if (len(data_cache) % self.__block_size) != 0 and self.__strict_mode:
            raise RuntimeError(f'Data is not aligned within {self.__block_size} bytes')

        if data_cache:
            yield data_cache


class ChunkReader:
    """ This class is like :class:`.Aligner` but helps to control number of block that will be read at a time
    """

    def __init__(self, data: IOProducer, block_size: int, *, strict_mode: bool = False):
        """Create a reader

        :param data: data to be read and aligned
        :param block_size: size of block in bytes that yielded data should be aligned to
        :param strict_mode: whether to raise an exception when the last block was not aligned
        """
        self.__block_size = block_size
        self.__strict_mode = strict_mode
        self.__aligner = Aligner(block_size, strict_mode=strict_mode)
        self.__data_generator = self.__aligner.iterate_data(data)

        self.__cached_chunk = b''
        self.__stop_reading = False
        self.__generator_exhausted = False

    @verify_value(min_blocks=lambda x: x > 0)
    @verify_value(max_blocks=lambda x: x > 0)
    def next_chunk(self, min_blocks: int, max_blocks: int) -> bytes:
        """ Return next chunk. The last block may not be aligned (it depends on the strict_mode parameter)

        :param min_blocks: minimum number of blocks to read
        :param max_blocks: maximum number of blocks to read
        """

        assert(max_blocks >= min_blocks)

        if self.__stop_reading or (self.__generator_exhausted and not self.__cached_chunk):
            self.__stop_reading = True
            raise StopIteration('Chunk reader exhausted')

        min_bytes = min_blocks * self.__block_size
        max_bytes = max_blocks * self.__block_size

        if min_bytes <= len(self.__cached_chunk) <= max_bytes:
            result = self.__cached_chunk[:max_bytes]
            self.__cached_chunk = self.__cached_chunk[max_bytes:]
            return result

        try:
            while not self.__generator_exhausted and len(self.__cached_chunk) < min_bytes:
                self.__cached_chunk += next(self.__data_generator)
        except StopIteration:
            # the last chunk may be huge
            self.__generator_exhausted = True

        result = self.__cached_chunk[:max_bytes]
        self.__cached_chunk = self.__cached_chunk[max_bytes:]

        if not result:
            raise StopIteration('Chunk reader exhausted')

        return result
