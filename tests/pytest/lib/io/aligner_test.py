import contextlib
import typing
import pytest

from pyknic.lib.io.aligner import Aligner, ChunkReader
from pyknic.lib.io import IOGenerator


class TestAligner:

    @pytest.mark.parametrize(
        'block_size, aligner_kwargs, input_data, result_data',
        [
            [2, dict(), (x for x in [b'b', b'b', b'b', b'bbb']), [b'bb', b'bbbb']],
            [2, dict(), (x for x in [b'bbbbbb']), [b'bbbbbb']],
            [3, dict(), (x for x in [b'bb', b'bb', b'b', b'b']), [b'bbb'] * 2],
            [2, dict(), (x for x in [b'b']), [b'b']],
            [2, {"strict_mode": False}, (x for x in [b'b']), [b'b']],
            [2, {"strict_mode": True}, (x for x in [b'bbbbbb']), [b'bbbbbb']],
            [2, {"strict_mode": True}, (x for x in [b'b', b'b', b'b', b'bbb']), [b'bb', b'bbbb']],
        ]
    )
    def test(
        self,
        block_size: int,
        aligner_kwargs: typing.Dict[str, typing.Any],
        input_data: IOGenerator,
        result_data: typing.List[bytes],
    ) -> None:
        aligner = Aligner(block_size, **aligner_kwargs)

        def result_keeper(iter_data: IOGenerator) -> typing.List[bytes]:
            result = []
            for i in iter_data:
                result.append(i)
            return result

        assert(result_keeper(aligner.iterate_data(input_data)) == result_data)

    def test_exception(self) -> None:
        aligner = Aligner(3, strict_mode=True)

        aligner_gen = aligner.iterate_data((x for x in [b'b']))
        with pytest.raises(RuntimeError):
            next(aligner_gen)


class TestChunkReader:

    @pytest.mark.parametrize(
        'block_size, aligner_kwargs, input_data, result_data',
        [
            [2, dict(), (x for x in [b'b', b'b', b'b', b'bbb']), [b'bb', b'bb', b'bb']],
            [2, dict(), (x for x in [b'bbbbbb']), [b'bb', b'bb', b'bb']],
            [3, dict(), (x for x in [b'bb', b'bb', b'b', b'b']), [b'bbb'] * 2],
            [2, dict(), (x for x in [b'b']), [b'b']],
            [2, {"strict_mode": False}, (x for x in [b'b']), [b'b']],
            [2, {"strict_mode": True}, (x for x in [b'bbbbbb']), [b'bb', b'bb', b'bb']],
            [2, {"strict_mode": True}, (x for x in [b'b', b'b', b'b', b'bbb']), [b'bb', b'bb', b'bb']],
        ]
    )
    def test_chunk_by_one(
        self,
        block_size: int,
        aligner_kwargs: typing.Dict[str, typing.Any],
        input_data: IOGenerator,
        result_data: typing.List[bytes],
    ) -> None:
        reader = ChunkReader(input_data, block_size, **aligner_kwargs)

        result = []

        with contextlib.suppress(StopIteration):
            while True:
                result.append(reader.next_chunk(1, 1))

        assert(result == result_data)

    def test_different_chunks(self) -> None:
        reader = ChunkReader([b'b', b'', b'bb', b'bbb', b'bbbb', b'b'], 2, )

        assert(reader.next_chunk(1, 3) == b'bb')
        assert(reader.next_chunk(3, 3) == b'bbbbbb')
        assert(reader.next_chunk(2, 3) == b'bbb')  # it is all that left

        reader = ChunkReader([b'b', b'', b'bb', b'bbb', b'bbbb', b'b'], 2, )
        assert(reader.next_chunk(10, 10) == b'bbbbbbbbbbb')

        reader = ChunkReader([b'b', b'', b'bb', b'bbb', b'bbbb', b'b'], 2, strict_mode=True)
        with pytest.raises(RuntimeError):
            _ = reader.next_chunk(10, 10)
