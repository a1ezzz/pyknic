# -*- coding: utf-8 -*-
# pyknic/lib/crypto/htpasswd.py
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

import abc
import contextlib
import pathlib
import re
import secrets
import typing

import argon2
import bcrypt

from pyknic.lib.registry import APIRegistry, register_api
from pyknic.lib.verify import verify_value


__default_passwd_checker_registry__ = APIRegistry()  # registry for pw-hash handlers


class HTPasswdHashCheckerProto(metaclass=abc.ABCMeta):
    """ This is a prototype for a single method that checks password
    """

    @abc.abstractmethod
    def match(self, password: str, hash_method: str, password_hash: str) -> bool:
        """ Return True if the password matches a hash or return False otherwise

        :param password: password to check
        :param hash_method: hashing method
        :param password_hash: hash to match to
        """
        raise NotImplementedError('This method is abstract')


@register_api(__default_passwd_checker_registry__, '2a')
@register_api(__default_passwd_checker_registry__, '2b')
@register_api(__default_passwd_checker_registry__, '2y')
class HTPasswdBCrypt(HTPasswdHashCheckerProto):
    """ Bcrypt password hasher.

    :note: It is better to prefer the "argon2id"
    """

    def match(self, password: str, hash_method: str, password_hash: str) -> bool:
        """ The :meth:`.HTPasswdHashCheckerProto.match` method implementation
        """

        suitable_methods = ('2a', '2b', '2y')
        if hash_method not in suitable_methods:
            raise ValueError(
                f'Hash method is incorrect -- {hash_method}. Suitable methods are: {", ".join(suitable_methods)}'
            )

        return bcrypt.checkpw(password.encode(), b'$' + hash_method.encode() + b'$' + password_hash.encode())


@register_api(__default_passwd_checker_registry__, 'argon2id')
class HTPasswdArgon2(HTPasswdHashCheckerProto):
    """ Argon2 password hasher.
    """

    def match(self, password: str, hash_method: str, password_hash: str) -> bool:
        """ The :meth:`.HTPasswdHashCheckerProto.match` method implementation
        """

        if hash_method != 'argon2id':
            raise ValueError(f'Hash method is incorrect -- {hash_method}. Suitable method is: argon2id')

        with contextlib.suppress(argon2.exceptions.VerifyMismatchError):
            ph = argon2.PasswordHasher()
            ph.verify(b'$' + hash_method.encode() + b'$' + password_hash.encode(), password.encode())
            return True

        return False


class HTPasswdEntry:
    """ This class represents a single entry of the htpasswd file
    """

    __htpasswd_regex__ = re.compile(r'^([^:]+):\$([^$]+)\$(.+)$')  # regexp to parse a string

    @verify_value(user_name=lambda x: ':' not in x)
    @verify_value(user_name=lambda x: len(x) > 0)
    @verify_value(hash_method=lambda x: x in __default_passwd_checker_registry__.ids())
    @verify_value(password_hash=lambda x: len(x) > 0)
    def __init__(self, user_name: str, hash_method: str, password_hash: str) -> None:
        """ Create an entry

        :param user_name: a user identity
        :param hash_method: hashing method
        :param password_hash: hashed password
        """

        self.__user_name = user_name
        self.__hash_method = hash_method
        self.__password_hash = password_hash

    def __str__(self) -> str:
        """ Return this entry as a string
        """
        return f'{self.__user_name}:${self.__hash_method}${self.__password_hash}'

    def user_name(self) -> str:
        """ Return a user identity
        """
        return self.__user_name

    def match(self, password: str) -> bool:
        """ Return True if the password matches a hash or return False otherwise

        :param password: password to check
        """
        checker_cls = __default_passwd_checker_registry__.get(self.__hash_method)
        return checker_cls().match(password, self.__hash_method, self.__password_hash)  # type: ignore[no-any-return]

    @classmethod
    def parse(cls, entry: str) -> 'HTPasswdEntry':
        """ Parse a string
        """

        parsed_entry = cls.__htpasswd_regex__.match(entry.strip())

        if parsed_entry is not None:
            u_name, hash_m, pass_h = parsed_entry.groups()
            return cls(u_name, hash_m, pass_h)

        raise ValueError('Unable to parse a line, it seams invalid')


class HTPasswd:
    """ This class describes a password database
    """

    def __init__(self) -> None:
        """ Create an empty database
        """
        self.__entries: typing.List[HTPasswdEntry] = []

    def add_entry(self, entry: HTPasswdEntry) -> None:
        """ Add an entry to a database

        :param entry: entry to add
        """
        self.__entries.append(entry)

    def match(self, user_name: str, password: str) -> bool:
        """ Return True if this database has an entry with the identity and corresponding password or return False
        otherwise

        :param user_name: a user identity
        :param password: password to check
        """
        user_name_matched = False

        for entry in self.__entries:
            if entry.user_name() == user_name:
                if entry.match(password):
                    return True

        if not user_name_matched:
            # make a pause
            secrets.compare_digest(b'', b'')

        return False

    @classmethod
    def read_file(cls, file_path: typing.Union[str, pathlib.Path]) -> 'HTPasswd':
        """ Read and parse the htpasswd file

        :param file_path: file to read and parse
        """

        passwd = HTPasswd()

        with open(file_path, 'r') as f:

            line = f.readline()
            while line != '':

                with contextlib.suppress(ValueError):
                    entry = HTPasswdEntry.parse(line)
                    passwd.add_entry(entry)

                line = f.readline()

        return passwd
