# -*- coding: utf-8 -*-

import base64

from pyknic.lib.fastapi.lobby_fingerprint import LobbyFingerprint


class TestLobbyFingerprint:

    __test_fingerprint__ = b'afCwlnEuf83Mfn75a8WFzDiFIxM6dObkeseFa5eEejs='
    __test_data__ = b'signature-test'
    __test_signature__ = b'5k6tq8apWZMQb1BWqCt9L9CpvXSX89os9sgXSkOhqnM='

    def test_sanity(self) -> None:
        _ = LobbyFingerprint.generate_fingerprint()

    def test_sign(self) -> None:
        fingerprint = LobbyFingerprint.deserialize(self.__test_fingerprint__)
        assert(str(fingerprint) == self.__test_fingerprint__.decode('ascii'))
        assert(fingerprint.sign(self.__test_data__) == base64.b64decode(self.__test_signature__))
        assert(fingerprint.sign(self.__test_data__, encode_base64=True) == self.__test_signature__)
