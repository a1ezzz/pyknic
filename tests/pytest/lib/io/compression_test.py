
import bz2
import gzip
import io
import lzma
import os
import typing

import pytest

from pyknic.lib.io.compression import __default_io_compressors_registry__, CompressorProto, GZipCompressor
from pyknic.lib.io.compression import BZip2Compressor, LZMACompressor


def test_abstract() -> None:
    pytest.raises(TypeError, CompressorProto)
    pytest.raises(NotImplementedError, CompressorProto.compress, None, None)
    pytest.raises(NotImplementedError, CompressorProto.decompress, None, None)


class TestCompressor:

    def reader(self, io_obj: typing.BinaryIO, batch_size: int) -> typing.Generator[bytes, None, None]:
        data = io_obj.read(batch_size)
        while len(data):
            yield data
            data = io_obj.read(batch_size)

    @pytest.mark.parametrize("compressor_cls", [GZipCompressor, BZip2Compressor, LZMACompressor])
    def test(self, compressor_cls: CompressorProto) -> None:
        original_data = ([b'b' * 1024] * 1024)

        compressor = compressor_cls()  # type: ignore[operator]
        compressed_data = list(compressor.compress(original_data))
        decompressed_data = list(compressor.decompress(compressed_data))

        assert(len(b''.join(compressed_data)) < (sum((len(x) for x in original_data)) / 10))
        assert(b''.join(decompressed_data) == b''.join(original_data))

    @pytest.mark.parametrize(
        "compressor_cls, native_compressor_constructor", [
            (GZipCompressor, lambda x: gzip.GzipFile(fileobj=x, mode='rb')),
            (BZip2Compressor, lambda x: bz2.BZ2File(x, mode='rb')),
            (LZMACompressor, lambda x: lzma.LZMAFile(x, mode='rb'))
        ]
    )
    def test_external_decompress(
        self,
        compressor_cls: CompressorProto,
        native_compressor_constructor: typing.Callable[[typing.BinaryIO], typing.BinaryIO]
    ) -> None:
        original_data = ([b'b' * 1024] * 1024)

        compressor = compressor_cls()  # type: ignore[operator]
        compressed_data = list(compressor.compress(original_data))

        io_bytes = io.BytesIO(b''.join(compressed_data))
        native_compressor_file = native_compressor_constructor(io_bytes)
        decompressed_data = native_compressor_file.read()

        assert(decompressed_data == b''.join(original_data))

    @pytest.mark.parametrize(
        "compressor_cls, native_decompressor_constructor", [
            (GZipCompressor, lambda x: gzip.GzipFile(fileobj=x, mode='wb')),
            (BZip2Compressor, lambda x: bz2.BZ2File(x, mode='wb')),
            (LZMACompressor, lambda x: lzma.LZMAFile(x, mode='wb'))
        ]
    )
    def test_external_compress(
        self,
        compressor_cls: CompressorProto,
        native_decompressor_constructor: typing.Callable[[typing.BinaryIO], typing.BinaryIO]
    ) -> None:
        original_data = ([b'b' * 1024] * 1024)

        io_bytes = io.BytesIO()
        native_decompressor_file = native_decompressor_constructor(io_bytes)
        native_decompressor_file.write(b''.join(original_data))
        native_decompressor_file.flush()
        native_decompressor_file.close()

        io_bytes.seek(0, os.SEEK_SET)

        compressor = compressor_cls()  # type: ignore[operator]
        decompressed_data = list(compressor.decompress(self.reader(io_bytes, 100)))

        assert(b''.join(decompressed_data) == b''.join(original_data))

    @pytest.mark.parametrize("compressor_cls", [GZipCompressor, BZip2Compressor, LZMACompressor])
    def test_corrupter_file(self, compressor_cls: CompressorProto) -> None:
        original_data = ([b'b' * 1024] * 1024)

        compressor = compressor_cls()  # type: ignore[operator]
        compressed_data = list(compressor.compress(original_data))
        io_bytes = io.BytesIO(b''.join(compressed_data))
        compressed_bytes = list(self.reader(io_bytes, 100))

        with pytest.raises(EOFError):
            _ = list(compressor.decompress(compressed_bytes[:-2]))

    @pytest.mark.parametrize(
        "compressor_name, decompressor_cls", [
            ('gzip', GZipCompressor),
            ('bzip2', BZip2Compressor),
            ('lzma', LZMACompressor)
        ]
    )
    def test_registry_compress(self, compressor_name: str, decompressor_cls: CompressorProto) -> None:
        original_data = ([b'b' * 1024] * 1024)
        compressor_cls = __default_io_compressors_registry__.get(compressor_name)

        compressed_data = list(compressor_cls().compress(original_data))
        decompressed_data = list(decompressor_cls().decompress(compressed_data))  # type: ignore[operator]
        assert (b''.join(decompressed_data) == b''.join(original_data))

    @pytest.mark.parametrize(
        "decompressor_name, compressor_cls", [
            ('gzip', GZipCompressor),
            ('bzip2', BZip2Compressor),
            ('lzma', LZMACompressor)
        ]
    )
    def test_registry_decompress(self, decompressor_name: str, compressor_cls: CompressorProto) -> None:
        original_data = ([b'b' * 1024] * 1024)
        decompressor_cls = __default_io_compressors_registry__.get(decompressor_name)

        compressed_data = list(compressor_cls().compress(original_data))  # type: ignore[operator]
        decompressed_data = list(decompressor_cls().decompress(compressed_data))
        assert (b''.join(decompressed_data) == b''.join(original_data))
