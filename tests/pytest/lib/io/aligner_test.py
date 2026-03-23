
import typing
import pytest

from pyknic.lib.io.aligner import Aligner
from pyknic.lib.io import IOGenerator


class TestAligner:

    @pytest.mark.parametrize(
        'block_size, aligner_kwargs, input_data, result_data',
        [
            [2, dict(), (x for x in [b'bbbbbb']), [b'bb'] * 3],
            [3, dict(), (x for x in [b'bb', b'bb', b'b', b'b']), [b'bbb'] * 2],
            [2, dict(), (x for x in [b'b']), [b'b']],
            [2, {"strict_mode": False}, (x for x in [b'b']), [b'b']],
            [2, {"strict_mode": True}, (x for x in [b'bbbbbb']), [b'bb'] * 3],
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
