# -*- coding: utf-8 -*-

import pytest

from pyknic.lib.crypto.random import random_bits, random_bytes, random_int


@pytest.mark.parametrize("bits_count", range(1, 100))
def test_random_bits(bits_count: int) -> None:

    bit_value = random_bits(bits_count)
    assert(0 <= bit_value <= ((2 ** bits_count) - 1))

    if bits_count >= 10:
        conjunctions = 0

        for _ in range(10):
            bit1 = random_bits(bits_count)
            bit2 = random_bits(bits_count)

            conjunctions += bit1 == bit2

        assert(conjunctions <= 1)


@pytest.mark.parametrize("int_value", range(1, 100))
def test_random_int(int_value: int) -> None:
    random_value = random_int(int_value)
    assert(0 <= random_value <= int_value)


@pytest.mark.parametrize("int_value", range(1000, 10000, 250))
def test_random_int_conjunctions(int_value: int) -> None:
    conjunctions = 0

    for _ in range(10):
        int1 = random_int(int_value)
        int2 = random_int(int_value)

        conjunctions += int1 == int2

    assert(conjunctions <= 1)


@pytest.mark.parametrize("length_value", range(1, 100))
def test_random_bytes(length_value: int) -> None:
    random_value = random_bytes(length_value)
    assert(len(random_value) == length_value)


@pytest.mark.parametrize("length_value", range(10, 100))
def test_random_bytes_conjunctions(length_value: int) -> None:
    conjunctions = 0

    for _ in range(10):
        b1 = random_bytes(length_value)
        b2 = random_bytes(length_value)

        conjunctions += b1 == b2

    assert(conjunctions <= 1)
