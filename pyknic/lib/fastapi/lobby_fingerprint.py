# -*- coding: utf-8 -*-
# pyknic/lib/fastapi/lobby_fingerprint.py
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

import base64
import secrets

from cryptography.hazmat.primitives import hashes, hmac

from pyknic.lib.verify import verify_value


class LobbyFingerprint:
    """This class wraps fingerprint routine and HMAC-signing things."""

    @verify_value(fingerprint=lambda x: len(x) == LobbyFingerprint.fingerprint_bytes())
    def __init__(self, fingerprint: bytes) -> None:
        """Create an object that may implement some functions with fingerprint.

        :param fingerprint: fingerprint to use
        """
        self.__fingerprint = fingerprint

    @classmethod
    def fingerprint_bytes(cls) -> int:
        """Return fixed number of bytes that this fingerprint has. In HMAC-SHA256 it must be the same size
        as 32 bytes (256 bit)
        """
        return 32

    def __str__(self) -> str:
        """Return fingerprint as a base64 encoded string."""
        return base64.b64encode(self.__fingerprint).decode('ascii')

    def sign(self, data_to_sign: bytes, encode_base64: bool = False) -> bytes:
        """Return signature of data.

        :param data_to_sign: data to sign
        :param encode_base64: whether signature should be return as is or as base64 encoded bytes
        """
        h = hmac.HMAC(self.__fingerprint, hashes.SHA256())
        h.update(data_to_sign)
        result = h.finalize()
        if encode_base64:
            result = base64.b64encode(result)
        return result

    @classmethod
    def generate_fingerprint(cls) -> 'LobbyFingerprint':
        """Return randomly generated sequence of bytes."""
        # TODO: check if it is secure enough (at the first glance it is ok but still)
        fingerprint = secrets.token_bytes(cls.fingerprint_bytes())
        return LobbyFingerprint(fingerprint)

    @classmethod
    def serialized_length(cls) -> int:
        """Return number of bytes required to represent base64 encoded fingerprint. In base64 every 3 bytes are
        encoded with 4 symbols so the target size is 44
        """
        return 44

    @classmethod
    def deserialize(cls, fingerprint: bytes) -> 'LobbyFingerprint':
        """Return fingerprint object from base64 encoded string.

        :param fingerprint: base64 encoded fingerprint
        """
        return LobbyFingerprint(base64.b64decode(fingerprint))
