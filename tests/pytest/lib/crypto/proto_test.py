
import pytest

from pyknic.lib.crypto.proto import CipherProto, BlockPaddingProto


def test_abstract() -> None:
    pytest.raises(TypeError, CipherProto)
    pytest.raises(NotImplementedError, CipherProto.block_size, None)
    pytest.raises(NotImplementedError, CipherProto.encrypt, None, (x for x in [b'bbbb']))
    pytest.raises(NotImplementedError, CipherProto.decrypt, None, (x for x in [b'bbbb']))

    pytest.raises(TypeError, BlockPaddingProto)
    pytest.raises(NotImplementedError, BlockPaddingProto.pad, None, (x for x in [b'bbbb']), 1)
    pytest.raises(NotImplementedError, BlockPaddingProto.undo_pad, None, (x for x in [b'bbbb']), 1)
