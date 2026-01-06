
from pyknic.lib.crypto.kdf import PBKDF2


class TestPBKDF2:

    def test(self) -> None:
        key = PBKDF2(b'foooooooooooooooooooooooo')

        assert(len(key.derived_key()) == 16)
        assert(len(key.salt()) == 64)
