# -*- coding: utf-8 -*-
# pyknic/lib/io/crypto/kdf.py
#
# Copyright (C) 2017-2026 the pyknic authors and contributors
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

from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC as C10yPBKDF2HMAC
from cryptography.hazmat.backends import default_backend

from pyknic.lib.verify import verify_value
from pyknic.lib.crypto.hash import __default_io_hashers_registry__
from pyknic.lib.crypto.random import random_bytes


class PBKDF2:
    """ Wrapper for Cryptography io PBKDF2 implementation with NIST recommendation and HMAC is used as pseudorandom
    function

    NIST recommendation can be read here:
    http://nvlpubs.nist.gov/nistpubs/Legacy/SP/nistspecialpublication800-132.pdf (Recommendation for Password-Based
    Key Derivation)
    """

    __minimum_key_length__ = 20
    """ Minimum key length is specified at Appendix A, Section A.1 of Recommendation for Password-Based
    Key Derivation by NIST
    """

    __minimum_salt_length__ = 16
    """ Minimum salt length is specified at Section 5.1 of Recommendation for Password-Based Key Derivation by NIST
    """

    __default_salt_length__ = 64
    """ Salt length value used by default
    """

    __default_digest_generator_name__ = 'sha256'
    """ Hash-generator that is used by default
    """

    __minimum_iterations_count__ = 1000
    """ Minimum iteration Count is specified at Section 5.2 of Recommendation for Password-Based Key Derivation by
    NIST
    """

    __default_iterations_count__ = 1000
    """ The iteration count used by default
    """

    __default_derived_key_length__ = 16
    """ Length of derived key used by default
    """

    @verify_value(key=lambda x: len(x) >= PBKDF2.__minimum_key_length__)
    @verify_value(salt=lambda x: x is None or len(x) >= PBKDF2.__minimum_salt_length__)
    @verify_value(iterations_count=lambda x: x is None or x >= PBKDF2.__minimum_iterations_count__)
    @verify_value(hash_fn_name=lambda x: x is None or __default_io_hashers_registry__.get(x))
    def __init__(
        self,
        key: typing.Union[bytes],
        salt: typing.Optional[bytes] = None,
        derived_key_length: typing.Optional[int] = None,
        iterations_count: typing.Optional[int] = None,
        hash_fn_name: typing.Optional[str] = None
    ):
        """ Generate new key (derived key) with PBKDF2 algorithm

        :param key: password
        :param salt: salt to use (if no salt was specified, then it will be generated automatically)
        :param derived_key_length: length of byte-sequence to generate
        :param iterations_count: iteration count
        :param hash_fn_name: name of hash function to be used with HMAC
        """

        self.__salt = salt if salt is not None else self.generate_salt()

        if derived_key_length is None:
            derived_key_length = self.__default_derived_key_length__

        if iterations_count is None:
            iterations_count = self.__default_iterations_count__

        if hash_fn_name is None:
            hash_fn_name = self.__class__.__default_digest_generator_name__

        hash_cls = __default_io_hashers_registry__.get(hash_fn_name)
        hash_obj = hash_cls()

        pbkdf2_obj = C10yPBKDF2HMAC(
            algorithm=hash_obj.c10y_algorithm(),
            length=derived_key_length,
            salt=self.__salt,
            iterations=iterations_count,
            backend=default_backend()
        )

        self.__derived_key = pbkdf2_obj.derive(key)

    def salt(self) -> bytes:
        """ Return salt value (that was given in constructor or created automatically)
        """
        return self.__salt

    def derived_key(self) -> bytes:
        """ Return derived key
        """
        return self.__derived_key

    @classmethod
    @verify_value(length=lambda x: x is None or x >= PBKDF2.__minimum_salt_length__)
    def generate_salt(cls, length: typing.Optional[int] = None) -> bytes:
        """ Generate salt that can be used by this object

        :param length: target salt length
        """
        return random_bytes(length if length is not None else cls.__default_salt_length__)
