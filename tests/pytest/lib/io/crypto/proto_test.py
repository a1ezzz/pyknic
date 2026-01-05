
import pytest

from pyknic.lib.io.crypto.proto import CipherProto


def test_abstract() -> None:
    pytest.raises(TypeError, CipherProto)
    pytest.raises(NotImplementedError, CipherProto.block_size, None)
    pytest.raises(NotImplementedError, CipherProto.encrypt, None, (x for x in [b'bbbb']))
    pytest.raises(NotImplementedError, CipherProto.decrypt, None, (x for x in [b'bbbb']))
