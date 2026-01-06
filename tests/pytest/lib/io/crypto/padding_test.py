# -*- coding: utf-8 -*-

import io
import pytest
import typing

from cryptography.hazmat.primitives.padding import PKCS7

from pyknic.lib.io.crypto.proto import BlockPaddingProto
from pyknic.lib.io.crypto.padding import SimplePadding, ZeroPadding, ShiftPadding, PKCS7Padding
from pyknic.lib.io.aio_wrapper import IOThrottler, cg


class TestSimplePadding:

    def test(self) -> None:
        padding = SimplePadding()
        assert(isinstance(padding, SimplePadding))
        assert(isinstance(padding, BlockPaddingProto))
        assert(padding.padding_symbol() == b'\x00')
        assert(padding.always_pad() is False)

        padding = SimplePadding(b'b', always_pad=False)
        assert(padding.padding_symbol() == b'b')
        assert(padding.always_pad() is False)

        padding = SimplePadding(b'c', always_pad=True)
        assert(padding.padding_symbol() == b'c')
        assert(padding.always_pad() is True)

    def test_concurrency_exceptions(self) -> None:
        padding = SimplePadding()

        next(padding.pad((x for x in [b'bbb']), 10))

        with pytest.raises(RuntimeError):
            next(padding.pad((x for x in [b'bbb']), 10))

        with pytest.raises(RuntimeError):
            next(padding.undo_pad((x for x in [b'bbb']), 10))

    def test_undo_pad_exceptions(self) -> None:
        padding = SimplePadding()
        with pytest.raises(RuntimeError):
            cg(padding.undo_pad((x for x in [b'bb']), 3))  # not enough data

        padding = SimplePadding()
        with pytest.raises(RuntimeError):
            cg(padding.undo_pad((x for x in [b'bbbb']), 3))  # not enough data

        padding = SimplePadding()
        assert(cg(padding.undo_pad((x for x in [b'bbbb']), 2)) == 4)  # this is ok

        padding = SimplePadding(always_pad=False)
        assert(cg(padding.undo_pad((x for x in [b'bbbb']), 2)) == 4)  # this is ok

        padding = SimplePadding(always_pad=True)
        with pytest.raises(RuntimeError):
            cg(padding.undo_pad((x for x in [b'bbbb']), 2))  # not enough data

        padding = SimplePadding(always_pad=True)
        assert(cg(padding.undo_pad((x for x in [b'bbbb\x00\x00']), 2)) == 4)  # this is ok

    @pytest.mark.parametrize(
        'padding_args, padding_kwargs, input_data, expected_data, input_block_size, output_block_size',
        [
            [tuple(), dict(), b'bbb', b'bbb\x00\x00\x00\x00\x00\x00\x00', 10, 10],
            [tuple(), dict(), b'bbb', b'bbb\x00', 2, 4],
            [(b'c', ), dict(), b'bb', b'bbccccc', 7, 7],
            [(b'c', ), dict(), b'bbbbb', b'bbbbb', 5, 5],
            [(b'c',), {"always_pad": True}, b'bbbbb', b'bbbbbccccc', 5, 10],
            [(b'c',), {"always_pad": False}, b'bbbbb', b'bbbbb', 5, 5],
        ]
    )
    def test_pad(
        self,
        padding_args: typing.Tuple[typing.Any, ...],
        padding_kwargs: typing.Dict[str, typing.Any],
        input_data: bytes,
        expected_data: bytes,
        input_block_size: int,
        output_block_size: int,
    ) -> None:
        result_io = io.BytesIO()

        padding = SimplePadding(*padding_args, **padding_kwargs)
        assert(cg(IOThrottler.sync_writer(
            padding.pad((x for x in [input_data]), input_block_size),
            result_io
        )) == output_block_size)
        assert(result_io.getvalue() == expected_data)

    @pytest.mark.parametrize(
        'padding_args, padding_kwargs, input_data, expected_data, input_block_size, output_block_size',
        [
            [tuple(), dict(), b'bbb\x00\x00\x00\x00\x00\x00\x00', b'bbb', 10, 3],
            [tuple(), dict(), b'bbb\x00', b'bbb', 2, 3],
            [(b'c',), dict(), b'bbccccc', b'bb', 7, 2],
            [(b'c',), dict(), b'bbbbb', b'bbbbb', 5, 5],
            [(b'c',), {"always_pad": True}, b'bbbbbccccc', b'bbbbb', 5, 5],
            [(b'c',), {"always_pad": False}, b'bbbbb', b'bbbbb', 5, 5],
        ]
    )
    def test_undo_pad(
        self,
        padding_args: typing.Tuple[typing.Any, ...],
        padding_kwargs: typing.Dict[str, typing.Any],
        input_data: bytes,
        expected_data: bytes,
        input_block_size: int,
        output_block_size: int,
    ) -> None:
        result_io = io.BytesIO()

        padding = SimplePadding(*padding_args, **padding_kwargs)

        assert(cg(IOThrottler.sync_writer(
            padding.undo_pad((x for x in [input_data]), input_block_size),
            result_io
        )) == output_block_size)
        assert(result_io.getvalue() == expected_data)


class TestZeroPadding:

    def test(self) -> None:
        padding = ZeroPadding()
        assert(isinstance(padding, SimplePadding))
        assert(isinstance(padding, BlockPaddingProto))
        assert(padding.padding_symbol() == b'\x00')
        assert(padding.always_pad() is True)


class TestShiftPadding:

    def test(self) -> None:
        padding = ShiftPadding()
        assert(isinstance(padding, SimplePadding))
        assert(isinstance(padding, BlockPaddingProto))
        assert(padding.padding_symbol() == b'\x00')
        assert(padding.always_pad() is True)

        padding = ShiftPadding(b'b')
        assert(padding.padding_symbol() == b'b')
        assert(padding.always_pad() is True)

    @pytest.mark.parametrize(
        'padding_args, padding_symbol',
        [
            [tuple(), b'\x00'],
            [(b'\x00', ), b'\x00'],
            [(b'c',), b'c'],
        ]
    )
    def test_pad_and_undo_pad(self, padding_args: typing.Tuple[typing.Any, ...], padding_symbol: bytes) -> None:
        result_io = io.BytesIO()
        padding = ShiftPadding(*padding_args)
        cg(IOThrottler.sync_writer(padding.pad((x for x in [b'bbb']), 10), result_io))

        result_bytes = result_io.getvalue()
        assert(result_bytes.startswith(padding_symbol))
        assert(result_bytes.endswith(padding_symbol))

        assert(result_bytes.lstrip(padding_symbol).rstrip(padding_symbol) == b'bbb')

        result_io = io.BytesIO()
        padding = ShiftPadding(*padding_args)
        cg(IOThrottler.sync_writer(padding.undo_pad((x for x in [result_bytes]), 10), result_io))
        assert(result_io.getvalue() == b'bbb')


class TestPKCS7Padding:

    @pytest.mark.parametrize(
        'input_data, block_size',
        [
            [b'bb', 2],
            [b'bbb', 2],
            [b'bbbb', 2]
        ]
    )
    def test(self, input_data: bytes, block_size: int) -> None:
        padding = PKCS7Padding()
        assert(isinstance(padding, BlockPaddingProto))

        result_io = io.BytesIO()
        padding = PKCS7Padding()
        cg(IOThrottler.sync_writer(padding.pad((x for x in [input_data]), block_size), result_io))
        result_bytes = result_io.getvalue()

        cryptography_obj = PKCS7(block_size * 8).padder()
        cryptography_obj.update(input_data)
        assert(result_bytes == (input_data + cryptography_obj.finalize()))

        result_io = io.BytesIO()
        padding = PKCS7Padding()
        cg(IOThrottler.sync_writer(padding.undo_pad((x for x in [result_bytes]), block_size), result_io))
        assert(result_io.getvalue() == input_data)

    def test_exceptions(self) -> None:
        input_data = b'bb'
        block_size = 10
        padding = PKCS7Padding()

        with pytest.raises(RuntimeError):
            cg(padding.pad((x for x in [input_data]), 256))  # block size is too big

        result_io = io.BytesIO()
        cg(IOThrottler.sync_writer(padding.pad((x for x in [input_data]), block_size), result_io))
        result_bytes = result_io.getvalue()

        with pytest.raises(RuntimeError):
            cg(padding.pad((x for x in [input_data]), block_size))  # the "pad" method is called already

        with pytest.raises(RuntimeError):
            cg(padding.undo_pad((x for x in [result_bytes]), block_size))  # the "pad" method is called already

        padding = PKCS7Padding()
        with pytest.raises(RuntimeError):
            cg(padding.undo_pad((x for x in [result_bytes]), 256))  # block size is too big

        with pytest.raises(RuntimeError):
            cg(padding.undo_pad((x for x in [b'b']), 10))  # data is too small

        with pytest.raises(RuntimeError):
            cg(padding.undo_pad((x for x in [b'b'] * 11), 10))  # data was not aligned

        with pytest.raises(RuntimeError):
            cg(padding.undo_pad((x for x in [b'b'] * 10), 10))  # data was not padded
