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

import os.path
import pathlib
import typing

from pyknic.lib.verify import verify_value
from pyknic.lib.uri import URI
from pyknic.lib.io_clients.proto import IOClientProto


@verify_value(path=lambda x: x.is_absolute())
def path_to_str(path: pathlib.PosixPath, relative_path: bool = False) -> str:
    # TODO: test it and document!
    if not relative_path:
        return os.path.abspath(path)  # TODO: Check whether it will work on Windows?!

    return os.path.abspath(path).lstrip('/')


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
        start_path: typing.Optional[pathlib.PosixPath] = None
    ):
        """Create a client

        :param uri: URI to connect to.
        :param start_path: Optional path to start with. If not defined then '/' is used
        """
        IOClientProto.__init__(self)

        self.__uri = uri
        self.__session_path = start_path if start_path else pathlib.PosixPath('/')

    def uri(self) -> URI:
        """Create URI this client was constructed with."""
        return self.__uri

    def join_path(self, *path: str) -> str:
        """Append current path with entries (directories) and return current path.

        :param path: path items to join
        """
        for p in path:
            self.__session_path /= p.lstrip('/')

        return self.session_path()

    @verify_value(path=lambda x: x is None or x.is_absolute())
    def session_path(self, path: typing.Optional[pathlib.PosixPath] = None) -> pathlib.PosixPath:
        """Set and/or get current session path.
        :param path: If defined then this path will be used as a current session path
        """
        if path is not None:
            self.__session_path = path

        return self.__session_path

    @verify_value(entry=lambda x: len(pathlib.PosixPath(x).parts) == 1)
    def entry_path(self, entry: str) -> pathlib.PosixPath:
        """Return path of a file that is stored inside a current session path.

        :param entry: inner file/directory name
        """
        return self.__session_path / entry
