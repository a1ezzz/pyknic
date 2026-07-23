# -*- coding: utf-8 -*-
# pyknic/lib/crypto/rsa.py
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

import cryptography.exceptions

from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives import hashes

from pyknic.lib.verify import verify_value


class InvalidSignature(Exception):
    """This exception is raised when a signature of a message does not match a public key
    """
    pass


class RSAPrivateKey:
    """ This class wraps RSA routine and represents a private key. For the moment encryption/decryption are
    not supported =)
    """

    def __init__(self, cryptography_obj: rsa.RSAPrivateKey) -> None:
        """ Create a new RSA private key object

        :param cryptography_obj: cryptography object to wrap

        :note: better to use :meth:`RSAPrivateKey.generate` or :meth:`RSAPrivateKey.import_pem` methods
        """
        self.__private_key = cryptography_obj

    def public_key(self) -> 'RSAPublicKey':
        """ Return related public key
        """
        return RSAPublicKey(self.__private_key.public_key())

    @verify_value(hash_name=lambda x: x.upper() in ('SHA128', 'SHA256', 'SHA512'))
    def sign(self, message: bytes, hash_name: str) -> bytes:
        """ Generate a signature of a message

        :param message: message to sign
        :param hash_name: a name of a hash function to use (one of 'SHA128', 'SHA256', 'SHA512')
        """

        hasher_cls = getattr(hashes, hash_name.upper())

        return self.__private_key.sign(
            message,
            padding.PSS(
                mgf=padding.MGF1(hasher_cls()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hasher_cls()
        )

    def export_pem(self, encryption_password: typing.Optional[bytes] = None) -> bytes:
        """ Export this key as PEM container

        :param encryption_password: if defined then this pem container will be encrypted
        """

        pem_encryption = serialization.NoEncryption()
        if encryption_password:
            pem_encryption = serialization.BestAvailableEncryption(encryption_password)  # type: ignore[assignment]

        return self.__private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=pem_encryption
        )

    @classmethod
    def generate(cls, key_size: int) -> 'RSAPrivateKey':
        """ Generate a random key

        :param key_size: a size of a new key
        """

        key = rsa.generate_private_key(public_exponent=65537, key_size=key_size)
        return cls(key)

    @classmethod
    def import_pem(cls, pem_data: bytes, encryption_password: typing.Optional[bytes] = None) -> 'RSAPrivateKey':
        """ Import private key from a previously exported PEM container.

        :param pem_data: data that has a private key
        :param encryption_password: a password with which a PEM was created
        """

        try:
            key = serialization.load_pem_private_key(pem_data, password=encryption_password)
            if not isinstance(key, rsa.RSAPrivateKey):
                raise ValueError(f'Non RSA key has been found -- {key.__class__.__name__}')
            return cls(key)
        except TypeError as e:
            if encryption_password is None:
                raise ValueError(f'Unable to import a key, may be a password is missing -- {e}') from e
            else:
                raise ValueError(f'Unable to import a key, may be unencrypted PEM is spotted -- {e}') from e


class RSAPublicKey:
    """ This class wraps RSA routine and represents a public key. For the moment encryption/decryption are
    not supported =)
    """

    def __init__(self, cryptography_obj: rsa.RSAPublicKey) -> None:
        """ Create a new RSA public key object

        :param cryptography_obj: cryptography object to wrap

        :note: better to use :meth:`RSAPrivateKey.public_key` or :meth:`RSAPublicKey.import_pem` methods
        """
        self.__public_key = cryptography_obj

    @verify_value(hash_name=lambda x: x.upper() in ('SHA128', 'SHA256', 'SHA512'))
    def verify(self, signature: bytes, message: bytes, hash_name: str) -> None:
        """ Check a signature of a message

        :param signature: signature to verify
        :param message: message to check
        :param hash_name: a name of a hash function to use (one of 'SHA128', 'SHA256', 'SHA512')
        """

        hasher_cls = getattr(hashes, hash_name.upper())

        try:
            self.__public_key.verify(
                signature,
                message,
                padding.PSS(
                    mgf=padding.MGF1(hasher_cls()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hasher_cls()
            )
        except cryptography.exceptions.InvalidSignature as e:
            raise InvalidSignature('Signature is invalid!') from e

    def export_pem(self) -> bytes:
        """ Export this key as PEM container
        """

        return self.__public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.PKCS1,
        )

    @classmethod
    def import_pem(cls, pem_data: bytes) -> 'RSAPublicKey':
        """ Import public key from a previously exported PEM container.

        :param pem_data: data that has a public key
        """
        key = serialization.load_pem_public_key(pem_data)
        if not isinstance(key, rsa.RSAPublicKey):
            raise ValueError(f'Non RSA key has been found -- {key.__class__.__name__}')
        return cls(key)
