# -*- coding: utf-8 -*-

import pytest

from pyknic.lib.crypto.hash import __default_io_hashers_registry__, HasherProto, BLAKE2b_64Hasher, BLAKE2s_32Hasher
from pyknic.lib.crypto.hash import MD5Hasher, SHA1Hasher, SHA224Hasher, SHA256Hasher, SHA384Hasher, SHA512Hasher
from pyknic.lib.crypto.hash import SHA512_224Hasher, SHA512_256Hasher, SHA3_224Hasher, SHA3_256Hasher, SHA3_384Hasher
from pyknic.lib.crypto.hash import SHA3_512Hasher


def test_abstract() -> None:
    pytest.raises(TypeError, HasherProto)
    pytest.raises(NotImplementedError, HasherProto.update, None, None)
    pytest.raises(NotImplementedError, HasherProto.digest, None)


class TestHasher:

    @pytest.mark.parametrize(
        'hasher_cls, result', [
            (
                BLAKE2b_64Hasher,
                b"W%\xbf\x81:\xae\xa7\xc5p\xd4 \xe8\x9a\xff\x1c\xfe\x90\x18&w\xf9\xcbl\xa8\xe6\xe5\xe3g\xbf\xa7\xa8l"
                b"L\xf0\xf6\xf3\x8f\x05\xfa\xc5\xc9(\xc6\xaf\rY\xa4{G\xc3m\xb4\x1c\xa0\x11\xfb*'6\x85bxo9"
            ),
            (
                BLAKE2s_32Hasher,
                b"\x0b\xbd\x9eD\xcd\xc9~\x88\x8e\xf8\xd0\n\x87\xd9]\xc6\x18'\xd6\xdfZ'L\xb1\x1d\x8c7\xe1\xd7x4^"
            ),
            (MD5Hasher, b"\x97I\xef\xed\xf4j\xcc[\xc8\x16A\xd8q]<\x8c"),
            (SHA1Hasher, b" \x91\xb9'\xdc\xb2\x90\xc0\xa3\xd0\x0e1F\xeb\xe6\x044\xc7[\xcb"),
            (SHA224Hasher, b"\xe9\x96\xd4ja\xdc\xc6\xc3`\xd7L\x945\xddk\xbe\x1d\xf28\xc45\xb3[\x96!\xcav\x89"),
            (
                SHA256Hasher,
                b"\xd9\x80\xf6\x08\x14G?)\xbc\x9e?g\xb8\xce\xfbo\xb2S\xa9\xc9\xc6\xc4\x80\xf0\xf7\x1e\x98\xf3\xc0\x9a"
                b"b\x8c"
            ),
            (
                SHA384Hasher,
                b"E\x05i\x08\xd1\xfa\xd656\x94ko`D\x92y\xef\xfc\xdd\x8a\x1b\x83\x16\x10\xaf\x0eV\xcf\xb6\xc0\xaa_\x1b"
                b"o\xe5\xb7y@\xfd@\xc4-D\xb1\xe5\xe7\xaa\\"
            ),
            (
                SHA512Hasher,
                b"\x9fs\xb7,\xce\xcb\xcc\xdc\xc2\xd5\xc2\x89\xc5:Fo\xbc\xd2\xaa\x06\xe0@p\xa9\x95=\xa1Yp\x9d\xfc\xfb"
                b"\\\xae\xcec\x0c\xa9X\xb2I\xcc'\x06\x970D\xc9\xa437\xc8D3[\xab\x88\x07\xaa\x0c\x19\xbf@2"
            ),
            (SHA512_224Hasher, b"\xe9kg\xb9\x01\xf2\xc5\tP:\x06{\\{\xbc=(S\xec\x9d\x8f\xe5\x13{\xe8A\x17\xbd"),
            (
                SHA512_256Hasher,
                b"\xa1\x86\x8a\xfd\xde>\x1b\xd7\x00}\xd5Y\x90EF#u7\xcf\xa9\xc2\x00s;\xceZ\x8a\xa8+\t\x8c5"
            ),
            (SHA3_224Hasher, b"\xa9?\xb5\x8d\x95\x19\x88x\x0cq\xa2dp&\xdc\x9a%\xe4\xb0\xeauxhn\x11\xb2\xd5\xc6"),
            (
                SHA3_256Hasher,
                b"\xdd\xdf\xfa$\x04\xf1x\xda[\xb4\xc1\x1b\xe0a\xa3\xdc\x1c\x85ye\x1fA+u\x17s%ip\x11\xc9\x1f"
            ),
            (
                SHA3_384Hasher,
                b"\x93\x93\x87\tB3\xd4\x1e\xd4!\xe3\xef\x06\xe7\x07\xa9\xaa\xdc\\O\xc02je\xd5y\x1c{1\x9c\x80\x8aF,C"
                b"O\xe5\t<\x7f`\x0e\xfb\ni\xaa9S"
            ),
            (
                SHA3_512Hasher,
                b"\xceDI\xc0\x10H3\x88\x8e\x96\x9b\xfd\xa6*@\xf7)o\xd1\xc0\xa9\x87\xae\xc6\xf2\t\xf8\xd1\xad\xfd!B"
                b"H\\\xbd\x0f|z&\xc9UN\x1bB\xc9eD\xfc5\x95\xa0\xf2G\x05n\x06\x96wv2W\xf4\xb0A"
            ),
        ]
    )
    def test_hashes(self, hasher_cls: HasherProto, result: bytes) -> None:
        sample_data = [b'Hello, world!'] * 10

        hasher = hasher_cls()  # type: ignore[operator]
        iter_list = list(hasher.update(sample_data))

        assert(hasher.digest() == result)
        assert(iter_list == sample_data)

    @pytest.mark.parametrize(
        'hasher_name, result', [
            (
                "blake2b_64",
                b"W%\xbf\x81:\xae\xa7\xc5p\xd4 \xe8\x9a\xff\x1c\xfe\x90\x18&w\xf9\xcbl\xa8\xe6\xe5\xe3g\xbf\xa7\xa8l"
                b"L\xf0\xf6\xf3\x8f\x05\xfa\xc5\xc9(\xc6\xaf\rY\xa4{G\xc3m\xb4\x1c\xa0\x11\xfb*'6\x85bxo9"
            ),
            (
                "blake2s_32",
                b"\x0b\xbd\x9eD\xcd\xc9~\x88\x8e\xf8\xd0\n\x87\xd9]\xc6\x18'\xd6\xdfZ'L\xb1\x1d\x8c7\xe1\xd7x4^"
            ),
            ("md5", b"\x97I\xef\xed\xf4j\xcc[\xc8\x16A\xd8q]<\x8c"),
            ("sha1", b" \x91\xb9'\xdc\xb2\x90\xc0\xa3\xd0\x0e1F\xeb\xe6\x044\xc7[\xcb"),
            ("sha224", b"\xe9\x96\xd4ja\xdc\xc6\xc3`\xd7L\x945\xddk\xbe\x1d\xf28\xc45\xb3[\x96!\xcav\x89"),
            (
                "sha256",
                b"\xd9\x80\xf6\x08\x14G?)\xbc\x9e?g\xb8\xce\xfbo\xb2S\xa9\xc9\xc6\xc4\x80\xf0\xf7\x1e\x98\xf3\xc0\x9a"
                b"b\x8c"
            ),
            (
                "sha384",
                b"E\x05i\x08\xd1\xfa\xd656\x94ko`D\x92y\xef\xfc\xdd\x8a\x1b\x83\x16\x10\xaf\x0eV\xcf\xb6\xc0\xaa_\x1b"
                b"o\xe5\xb7y@\xfd@\xc4-D\xb1\xe5\xe7\xaa\\"
            ),
            (
                "sha512",
                b"\x9fs\xb7,\xce\xcb\xcc\xdc\xc2\xd5\xc2\x89\xc5:Fo\xbc\xd2\xaa\x06\xe0@p\xa9\x95=\xa1Yp\x9d\xfc\xfb"
                b"\\\xae\xcec\x0c\xa9X\xb2I\xcc'\x06\x970D\xc9\xa437\xc8D3[\xab\x88\x07\xaa\x0c\x19\xbf@2"
            ),
            ("sha512_224", b"\xe9kg\xb9\x01\xf2\xc5\tP:\x06{\\{\xbc=(S\xec\x9d\x8f\xe5\x13{\xe8A\x17\xbd"),
            (
                "sha512_256",
                b"\xa1\x86\x8a\xfd\xde>\x1b\xd7\x00}\xd5Y\x90EF#u7\xcf\xa9\xc2\x00s;\xceZ\x8a\xa8+\t\x8c5"
            ),
            ("sha3_224", b"\xa9?\xb5\x8d\x95\x19\x88x\x0cq\xa2dp&\xdc\x9a%\xe4\xb0\xeauxhn\x11\xb2\xd5\xc6"),
            (
                "sha3_256",
                b"\xdd\xdf\xfa$\x04\xf1x\xda[\xb4\xc1\x1b\xe0a\xa3\xdc\x1c\x85ye\x1fA+u\x17s%ip\x11\xc9\x1f"
            ),
            (
                "sha3_384",
                b"\x93\x93\x87\tB3\xd4\x1e\xd4!\xe3\xef\x06\xe7\x07\xa9\xaa\xdc\\O\xc02je\xd5y\x1c{1\x9c\x80\x8aF,C"
                b"O\xe5\t<\x7f`\x0e\xfb\ni\xaa9S"
            ),
            (
                "sha3_512",
                b"\xceDI\xc0\x10H3\x88\x8e\x96\x9b\xfd\xa6*@\xf7)o\xd1\xc0\xa9\x87\xae\xc6\xf2\t\xf8\xd1\xad\xfd!B"
                b"H\\\xbd\x0f|z&\xc9UN\x1bB\xc9eD\xfc5\x95\xa0\xf2G\x05n\x06\x96wv2W\xf4\xb0A"
            ),
        ]
    )
    def test_registry(self, hasher_name: str, result: bytes) -> None:
        sample_data = [b'Hello, world!'] * 10

        hasher_cls = __default_io_hashers_registry__.get(hasher_name)
        hasher = hasher_cls()
        iter_list = list(hasher.update(sample_data))

        assert (hasher.digest() == result)
        assert (iter_list == sample_data)
