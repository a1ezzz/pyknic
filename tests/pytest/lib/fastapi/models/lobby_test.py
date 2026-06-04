# -*- coding: utf-8 -*-

from pyknic.lib.fastapi.models.lobby import LobbyJWTPayload


class TestLobbyJWTPayload:

    def test(self) -> None:
        jwt = LobbyJWTPayload.generate(
            10, 'subject1', 'aaa_policy1', '127.0.0.1', 8080, 'users'
        )
        assert(isinstance(jwt, LobbyJWTPayload))
