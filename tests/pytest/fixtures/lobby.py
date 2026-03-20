# -*- coding: utf-8 -*-
# tests/pytest/fixtures/lobby.py
#
# Copyright (C) 2026 the pyknic authors and contributors
# <see AUTHORS file>
#
# This file is part of pyknic.
#
# pyknic is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# pyknic is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with pyknic.  If not, see <http://www.gnu.org/licenses/>.

import typing
import pytest

from pyknic.lib.bellboy.app import LobbyClient
from pyknic.lib.bellboy.secret_backend import SharedMemorySecretBackend, SecretBackend


@pytest.fixture
def lobby_shm_secrets() -> typing.Generator[
    typing.Callable[[str, str], typing.Coroutine[None, None, None]], None, None
]:
    secret_backend = SecretBackend(SharedMemorySecretBackend())
    saved_urls = []

    async def secret_saver(lobby_url: str, token: str) -> None:
        secret_backend.set_secret(lobby_url, await LobbyClient.fingerprint(lobby_url), token)
        saved_urls.append(lobby_url)

    yield secret_saver

    for url in saved_urls:
        secret_backend.pop_secret(url)
