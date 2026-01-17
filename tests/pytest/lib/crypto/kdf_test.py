
from pyknic.lib.crypto.kdf import PBKDF2


class TestPBKDF2:

    def test(self) -> None:
        key = PBKDF2(b'foooooooooooooooooooooooo')

        assert(len(key.derived_key()) == 16)
        assert(len(key.salt()) == 64)
        assert(key.iterations() == PBKDF2.__default_iterations_count__)
        assert(key.hash_name() == PBKDF2.__default_digest_generator_name__)
