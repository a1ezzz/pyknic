
import io
import typing

import pytest

from pyknic.lib.io.clients.proto import PartsUploaderProto, NonSequentialPartNumbers, InvalidPartSize
from pyknic.lib.io.clients.parts_uploader import BasePartsUploader


class TestBasePartsUploader:

    class SampleUploader(BasePartsUploader):

        def __init__(self, part_size: int):
            BasePartsUploader.__init__(self, part_size)
            self.io = io.BytesIO()
            self.part_size = part_size

        def __enter__(self) -> 'BasePartsUploader':
            return self

        def _finalize(self, exc_val: typing.Optional[BaseException] = None) -> None:
            pass

        def _upload_part(self, data: bytes, part_number: int) -> None:
            self.io.seek(self.part_size * part_number, io.SEEK_SET)
            self.io.write(data)

    def test_abstract(self) -> None:
        pytest.raises(TypeError, BasePartsUploader)
        pytest.raises(NotImplementedError, PartsUploaderProto.__enter__, None)
        pytest.raises(NotImplementedError, BasePartsUploader._upload_part, None, b'', 0)
        pytest.raises(NotImplementedError, BasePartsUploader._finalize, None, None, {1, 2, 3})

    def test(self) -> None:

        uploader = TestBasePartsUploader.SampleUploader(part_size=10)
        with uploader as u:
            u.upload_part(b'b' * 10, 1)
            u.upload_part(b'c' * 5, 2)
            u.upload_part(b'a' * 10, 0)

        assert(uploader.io.getvalue() == (b'a' * 10 + b'b' * 10 + b'c' * 5))

    def test_no_intermediate_chunk_exception(self) -> None:
        uploader = TestBasePartsUploader.SampleUploader(part_size=10)

        with pytest.raises(NonSequentialPartNumbers):
            with uploader as u:
                u.upload_part(b'a' * 10, 0)
                u.upload_part(b'c' * 5, 2)

    def test_duplicate_chunks_exception(self) -> None:
        uploader = TestBasePartsUploader.SampleUploader(part_size=10)

        with pytest.raises(NonSequentialPartNumbers):
            with uploader as u:
                u.upload_part(b'a' * 10, 0)
                u.upload_part(b'c' * 5, 0)

    def test_no_double_final_chunks_exception(self) -> None:
        uploader = TestBasePartsUploader.SampleUploader(part_size=10)

        with pytest.raises(NonSequentialPartNumbers):
            with uploader as u:
                u.upload_part(b'a' * 10, 0)
                u.upload_part(b'b' * 5, 1)
                u.upload_part(b'c' * 5, 2)

    def test_huge_size_exception(self) -> None:
        uploader = TestBasePartsUploader.SampleUploader(part_size=10)

        with pytest.raises(InvalidPartSize):
            with uploader as u:
                u.upload_part(b'a' * 11, 0)

    def test_intermediate_final_chunk_exception(self) -> None:
        uploader = TestBasePartsUploader.SampleUploader(part_size=10)

        with pytest.raises(NonSequentialPartNumbers):
            with uploader as u:
                u.upload_part(b'a' * 10, 0)
                u.upload_part(b'c' * 5, 2)
                with pytest.raises(InvalidPartSize):
                    u.upload_part(b'b' * 5, 1)

    def test_intermediate_chunk_exception(self) -> None:
        uploader = TestBasePartsUploader.SampleUploader(part_size=10)

        with pytest.raises(NonSequentialPartNumbers):
            with uploader as u:
                u.upload_part(b'a' * 10, 0)
                u.upload_part(b'c' * 10, 2)
                with pytest.raises(InvalidPartSize):
                    u.upload_part(b'b' * 5, 1)
