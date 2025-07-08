# -*- coding: utf-8 -*-
# pyknic/lib/bellboy/client.py
#
# Copyright (C) 2025 the pyknic authors and contributors
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

import json

import aiohttp


from pyknic.lib.fastapi.lobby_fingerprint import LobbyFingerprint
from pyknic.lib.fastapi.models.lobby import LobbyServerFingerprint, LobbyCommandRequest
from pyknic.lib.fastapi.headers import FastAPIHeaders
from pyknic.lib.bellboy.error import BellboyCLIError
from pyknic.lib.bellboy.console import BellboyPromptParser


class LobbyClient:
    """This class wraps API calls routine.
    """

    def __init__(self, url: str, token: str | None = None):
        """Create a new client.

        :param url: URL to connect to.
        :param token: Token to authenticate with.
        """
        self.__url = url
        self.__token = token

    def url(self) -> str:
        """Return URL this client is connected to."""
        return self.__url

    async def fingerprint(self, session: aiohttp.ClientSession) -> LobbyFingerprint:
        """Return server's fingerprint.

        :param session: HTTP-client to use
        """
        # TODO: persist it and check it
        async with session.get(f'{self.__url}/fingerprint') as response:

            if response.status != 200:
                raise BellboyCLIError('Unable to fetch fingerprint')

            fingerprint_model = LobbyServerFingerprint.model_validate(await response.json())
            return LobbyFingerprint.deserialize(fingerprint_model.fingerprint.encode('ascii'))

    def set_token(self, token: str) -> None:
        """Override client token

        :param token: New token to authenticate with
        """
        self.__token = token

    async def secure_request(
        self,
        fingerprint: LobbyFingerprint,
        session: aiohttp.ClientSession,
        method_name: str,
        path: str | None = None,
        data: str | bytes | None = None
    ) -> bytes:
        """Make a secure request and return bytes that this request returns.

        :param fingerprint: allowed server's fingerprint to check a response
        :param session: HTTP-client to use
        :param method_name: HTTP-method to use (like 'get' or 'post')
        :param path: URL path
        :param data: Data to send with request
        """

        if self.__token is None:
            raise BellboyCLIError('Token is not set')

        auth_headers = {"Authorization": f"Bearer {self.__token}"}

        session_method = getattr(session, method_name)
        async with session_method(f'{self.__url}{path if path else ""}', headers=auth_headers, data=data) as response:
            if response.status != 200:
                raise BellboyCLIError(f'API request failed with status code {response.status}')

            binary_body = await response.content.read()
            signature = fingerprint.sign(binary_body, encode_base64=True).decode('ascii')

            if response.headers[FastAPIHeaders.fingerprint.value] != signature:
                raise BellboyCLIError(
                    'Response signature mismatch! Consider to restart session and validate connectivity'
                )
            return binary_body  # type: ignore[no-any-return]

    async def command_request(
        self, fingerprint: LobbyFingerprint, session: aiohttp.ClientSession, parser: BellboyPromptParser
    ) -> bytes:
        """Send command to a server.

        :param fingerprint: allowed server's fingerprint to check a response
        :param session: HTTP-client to use
        :param parser: command to sent
        """
        # TODO: check types for a command parameters that this command has

        request = LobbyCommandRequest(
            name=parser.command(), args=parser.args(), kwargs=parser.kwargs(), cargs=parser.cargs()
        )
        request_json = json.dumps(request.model_dump(mode='json'))

        return await self.secure_request(fingerprint, session, 'post', data=request_json)
