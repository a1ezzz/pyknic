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


from pyknic.lib.io import IOGenerator


class Aligner:
    """This class helps to chop IOGenerator into length-fixed blocks
    """

    def __init__(self, block_size: int, *, strict_mode: bool = False):
        """Create a new aligner

        :param block_size: size of block in bytes that should be yield
        :param strict_mode: whether to raise an exception when the last block was not aligned
        """
        self.__block_size = block_size
        self.__strict_mode = strict_mode

    def iterate_data(self, data: IOGenerator) -> IOGenerator:
        """Chop data into blocks/chunks
        """

        data_cache = b''
        for i in data:
            data_cache += i

            while len(data_cache) > self.__block_size:
                yield data_cache[:self.__block_size]
                data_cache = data_cache[self.__block_size:]

        if len(data_cache) != self.__block_size and self.__strict_mode:
            raise RuntimeError(f'Data is not aligned within {self.__block_size} bytes')

        if data_cache:
            yield data_cache
