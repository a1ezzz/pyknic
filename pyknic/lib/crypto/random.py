# -*- coding: utf-8 -*-
# pyknic/lib/crypto/random.py
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

import math
import os
import sys

from pyknic.lib.verify import verify_value


"""This module generates random data secure enough for cryptography purpose.

see also: https://cryptography.io/en/latest/random-numbers/
"""


@verify_value(bits_count=lambda x: x > 0)
def random_bits(bits_count: int) -> int:
    """Random generator that produces the specified number of random bits. The result is a non-negative integer.

    :param bits_count: random bits to generate
    :return: int
    """
    bytes_count = int(math.ceil(bits_count / 8))
    random_value = int.from_bytes(os.urandom(bytes_count), byteorder=sys.byteorder)
    result_bits = bytes_count * 8

    if result_bits > bits_count:
        random_value = (random_value >> (result_bits - bits_count))

    return random_value


@verify_value(maximum_value=lambda x: x > 0)
def random_int(maximum_value: int) -> int:
    """Random generator that produces a single integer that resides between 0 and the "maximum_value".
    The result is a non-negative value.

    :param maximum_value: maximum integer value
    :return: int
    """

    if maximum_value == 1:
        return random_bits(1)

    bits = math.floor(math.log2(maximum_value))
    result = random_bits(bits) + random_int(maximum_value - ((2 ** bits) - 1))
    return result


@verify_value(bytes_count=lambda x: x >= 0)
def random_bytes(bytes_count: int) -> bytes:
    """Generate random bytes sequence

    :param bytes_count: sequence length
    :return: bytes
    """
    return bytes([random_bits(8) for x in range(bytes_count)])
