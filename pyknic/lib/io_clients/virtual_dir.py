# -*- coding: utf-8 -*-
# pyknic/lib/io_clients/virtual_dir.py
#
# Copyright (C) 2018-2025 the pyknic authors and contributors
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

import os
import typing
import pathlib

from pyknic.lib.verify import verify_value
from pyknic.lib.uri import URI
from pyknic.lib.io_clients.proto import IOClientProto


class VirtualDirectoryClient(IOClientProto):
    """This class may be used as a basic class for network clients, that does not keep connection between
    capabilities calls. That type of clients may create connection for each request. In this case it is important
    to save current session directory, because it influences calls behaviour. This class helps to save and
    to change current session directory during such calls."""

    @classmethod
    def create_client(cls, uri: URI) -> 'VirtualDirectoryClient':
        """Basic client creation."""
        return cls(uri)  # type: ignore[no-any-return]  # mypy issue

    @verify_value(start_path=lambda x: x is None or x.is_absolute())
    def __init__(
        self,
        uri: URI,
        start_path: typing.Optional[pathlib.Path] = None,
        directory_sep: typing.Optional[str] = None
    ):
        """Create a client

        :param uri: URI to connect to.
        :param start_path: Optional path to start with. If not defined then os.sep is used
        :param directory_sep: Symbol ('/' or '\') that is used to separate entries inside a path
        (os.sep is used by default)
        """
        IOClientProto.__init__(self)

        if directory_sep is not None and directory_sep not in ('/', '\\'):
            raise ValueError('Invalid directory separator')

        self.__uri = uri
        self.__session_path = start_path if start_path else pathlib.Path(os.sep)
        self.__directory_sep = directory_sep if directory_sep != os.sep else None

    def uri(self) -> URI:
        """Create URI this client was constructed with."""
        return self.__uri

    def join_path(self, *path: str) -> str:
        """Append current path with entries (directories) and return current path.

        :param path: path items to join
        """
        for p in path:
            self.__session_path /= p.lstrip(os.sep)

        return self.session_path()

    def __to_str(self, path: pathlib.Path) -> str:
        """Convert a path to a string.

        :param path: a path to convert
        """
        result = str(path)

        if self.__directory_sep:
            result = result.replace(os.sep, self.__directory_sep)

        return result

    @verify_value(path=lambda x: x is None or x.is_absolute())
    def session_path(self, path: typing.Optional[pathlib.Path] = None) -> str:
        """Set and/or get current session path.
        :param path: If defined then this path will be used as a current session path.
        """
        if path is not None:
            self.__session_path = path

        return self.__to_str(self.__session_path)

    def file_path(self, file: str) -> str:
        """Return path of a file that is stored inside a current session path.

        :param file: file name
        """
        return self.__to_str(self.__session_path / file.lstrip(os.sep))
