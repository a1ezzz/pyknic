# -*- coding: utf-8 -*-
# pyknic/lib/crypto/hash.py
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

import typing

from abc import abstractmethod

from cryptography.hazmat.primitives import hashes as c10y_hashes
from cryptography.hazmat.primitives.hashes import HashAlgorithm as C10yHashAlgorithm

from pyknic.lib.io import IOGenerator
from pyknic.lib.registry import APIRegistry, register_api
from pyknic.lib.crypto.proto import HasherProto

__default_io_hashers_registry__ = APIRegistry()


class CryptographyHasherAdapter(HasherProto):
    """This is an adapter for cryptography hashers.
    """

    def __init__(self) -> None:
        """Create a new hasher."""
        HasherProto.__init__(self)
        self.__hasher = self.__create_hasher()
        self.__digest: typing.Optional[bytes] = None

    @abstractmethod
    def _hasher_name(self) -> str:
        """Return class name from the cryptography library that implement required hash algorithm."""
        raise NotImplementedError('This method is abstract')

    def _hasher_args(self) -> typing.Tuple[typing.Any, ...]:
        """Return args required for hasher object creation
        """
        return tuple()

    def __create_hasher(self) -> c10y_hashes.Hash:
        """Create a new object from the cryptography library."""
        hash_algo = self.c10y_algorithm()
        if hash_algo is None:
            raise RuntimeError('No suitable algorithm available')

        return c10y_hashes.Hash(hash_algo)

    def update(self, source: IOGenerator) -> IOGenerator:
        """The :meth:`.HasherProto.update` method implementation."""
        self.__hasher = self.__create_hasher()

        for chunk in source:
            self.__hasher.update(chunk)
            yield chunk

        self.__digest = self.__hasher.finalize()

    def digest(self) -> bytes:
        """The :meth:`.HasherProto.digest` method implementation."""
        if self.__digest is None:
            raise ValueError('Digest is not available. Please call the "update" method first.')
        return self.__digest

    def c10y_algorithm(self) -> typing.Optional[C10yHashAlgorithm]:
        """The :meth:`.HasherProto.c10y_algorithm` method implementation."""
        hash_algo = getattr(c10y_hashes, self._hasher_name())
        hash_args = self._hasher_args()

        return hash_algo(*hash_args)  # type: ignore[no-any-return]


@register_api(__default_io_hashers_registry__, "blake2b_64")
class BLAKE2b_64Hasher(CryptographyHasherAdapter):

    def _hasher_name(self) -> str:
        """The :meth:`.CryptographyHasherAdapter._hasher_name` method implementation."""
        return 'BLAKE2b'

    def _hasher_args(self) -> typing.Tuple[typing.Any, ...]:
        """The :meth:`.CryptographyHasherAdapter._hasher_args` method implementation."""
        return (64, )


@register_api(__default_io_hashers_registry__, "blake2s_32")
class BLAKE2s_32Hasher(CryptographyHasherAdapter):

    def _hasher_name(self) -> str:
        """The :meth:`.CryptographyHasherAdapter._hasher_name` method implementation."""
        return 'BLAKE2s'

    def _hasher_args(self) -> typing.Tuple[typing.Any, ...]:
        """The :meth:`.CryptographyHasherAdapter._hasher_args` method implementation."""
        return (32, )


@register_api(__default_io_hashers_registry__, "md5")
class MD5Hasher(CryptographyHasherAdapter):

    def _hasher_name(self) -> str:
        """The :meth:`.CryptographyHasherAdapter._hasher_name` method implementation."""
        return 'MD5'


@register_api(__default_io_hashers_registry__, "sha1")
class SHA1Hasher(CryptographyHasherAdapter):

    def _hasher_name(self) -> str:
        """The :meth:`.CryptographyHasherAdapter._hasher_name` method implementation."""
        return 'SHA1'


@register_api(__default_io_hashers_registry__, "sha224")
class SHA224Hasher(CryptographyHasherAdapter):

    def _hasher_name(self) -> str:
        """The :meth:`.CryptographyHasherAdapter._hasher_name` method implementation."""
        return 'SHA224'


@register_api(__default_io_hashers_registry__, "sha256")
class SHA256Hasher(CryptographyHasherAdapter):

    def _hasher_name(self) -> str:
        """The :meth:`.CryptographyHasherAdapter._hasher_name` method implementation."""
        return 'SHA256'


@register_api(__default_io_hashers_registry__, "sha384")
class SHA384Hasher(CryptographyHasherAdapter):

    def _hasher_name(self) -> str:
        """The :meth:`.CryptographyHasherAdapter._hasher_name` method implementation."""
        return 'SHA384'


@register_api(__default_io_hashers_registry__, "sha512")
class SHA512Hasher(CryptographyHasherAdapter):

    def _hasher_name(self) -> str:
        """The :meth:`.CryptographyHasherAdapter._hasher_name` method implementation."""
        return 'SHA512'


@register_api(__default_io_hashers_registry__, "sha512_224")
class SHA512_224Hasher(CryptographyHasherAdapter):

    def _hasher_name(self) -> str:
        """The :meth:`.CryptographyHasherAdapter._hasher_name` method implementation."""
        return 'SHA512_224'


@register_api(__default_io_hashers_registry__, "sha512_256")
class SHA512_256Hasher(CryptographyHasherAdapter):

    def _hasher_name(self) -> str:
        """The :meth:`.CryptographyHasherAdapter._hasher_name` method implementation."""
        return 'SHA512_256'


@register_api(__default_io_hashers_registry__, "sha3_224")
class SHA3_224Hasher(CryptographyHasherAdapter):

    def _hasher_name(self) -> str:
        """The :meth:`.CryptographyHasherAdapter._hasher_name` method implementation."""
        return 'SHA3_224'


@register_api(__default_io_hashers_registry__, "sha3_256")
class SHA3_256Hasher(CryptographyHasherAdapter):

    def _hasher_name(self) -> str:
        """The :meth:`.CryptographyHasherAdapter._hasher_name` method implementation."""
        return 'SHA3_256'


@register_api(__default_io_hashers_registry__, "sha3_384")
class SHA3_384Hasher(CryptographyHasherAdapter):

    def _hasher_name(self) -> str:
        """The :meth:`.CryptographyHasherAdapter._hasher_name` method implementation."""
        return 'SHA3_384'


@register_api(__default_io_hashers_registry__, "sha3_512")
class SHA3_512Hasher(CryptographyHasherAdapter):

    def _hasher_name(self) -> str:
        """The :meth:`.CryptographyHasherAdapter._hasher_name` method implementation."""
        return 'SHA3_512'
