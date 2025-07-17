# -*- coding: utf-8 -*-
# pyknic/lib/io_clients/virtual_dir.py
#
# Copyright (C) 2017-2025 the pyknic authors and contributors
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

import asyncio
import os
import pathlib
import typing

from pyknic.lib.uri import URI, URIQuery
from pyknic.lib.io_clients.virtual_dir import VirtualDirectoryClient
from pyknic.lib.verify import verify_value

# TODO: register client with registry!


class LocalClient(VirtualDirectoryClient):
    """Local files implementation of :class:`.IOClientProto`."""

    @classmethod
    def create_client(cls, uri: URI) -> 'VirtualDirectoryClient':
        """Basic client creation."""
        client_kwargs = dict()

        if uri.query:
            query = URIQuery.parse(uri.query)

            if 'block_size' in query:
                client_kwargs['block_size'] = query.single_parameter('block_size', int)

        return cls(uri, **client_kwargs)  # type: ignore[no-any-return]

    @verify_value(block_size=lambda x: x is None or x >= 4096)  # min block size is 4K
    def __init__(
        self,
        uri: URI,
        block_size: typing.Optional[int] = None,
    ) -> None:
        """Create a new client

        :param uri: URI with which this client should be created. If uri has the "path" attribute, then this path
        will be used as a start point
        :param block_size: number of bytes to copy at a time
        """

        VirtualDirectoryClient.__init__(self, uri)
        self.__block_size = block_size if block_size is not None else 4096

        if uri.path is not None:
            self.__change_directory(os.sep + uri.path)

    def current_directory(self) -> str:
        """The :meth:`.IOClientProto.current_directory` method implementation."""
        return self.session_path()

    def __change_directory(self, path: str) -> str:
        """Change current session directory to the specified one

        :param path: new session directory
        """
        path = self.session_path(pathlib.Path(path))
        if not pathlib.Path(path).is_dir():
            raise NotADirectoryError(f'No such directory: {path}')
        return path

    async def change_directory(self, path: str) -> str:
        """The :meth:`.IOClientProto.change_directory` method implementation."""
        return self.__change_directory(path)

    async def list_directory(self) -> typing.Tuple[str, ...]:
        """The :meth:`.IOClientProto.list_directory` method implementation."""
        path = pathlib.Path(self.session_path())
        return tuple(x.name for x in path.iterdir())

    async def make_directory(self, directory_name: str) -> None:
        """The :meth:`.IOClientProto.make_directory` method implementation."""
        path = pathlib.Path(self.session_path()) / directory_name
        path.mkdir(exist_ok=False, parents=False)

    async def remove_directory(self, directory_name: str) -> None:
        """The :meth:`.IOClientProto.remove_directory` method implementation."""
        path = pathlib.Path(self.session_path()) / directory_name
        path.rmdir()

    async def __copy(self, from_fo: typing.IO[bytes], to_fo: typing.IO[bytes]) -> None:
        """Copy files from one to another.

        :param from_fo: file to copy
        :param to_fo: file to copy to
        """
        from_fo.seek(0)
        to_fo.truncate(0)
        to_fo.seek(0)

        next_block = from_fo.read(self.__block_size)

        while next_block:
            await asyncio.sleep(0)  # aio-loop should work too
            to_fo.write(next_block)
            await asyncio.sleep(0)  # aio-loop should work too
            next_block = from_fo.read(self.__block_size)

    async def upload_file(self, remote_file_name: str, local_file_obj: typing.IO[bytes]) -> None:
        """The :meth:`.IOClientProto.upload_file` method implementation."""
        path = self.file_path(remote_file_name)
        with open(path, mode='wb') as f_remote:
            await self.__copy(local_file_obj, f_remote)

    async def remove_file(self, file_name: str) -> None:
        """The :meth:`.IOClientProto.remove_file` method implementation."""
        path = pathlib.Path(self.session_path()) / file_name
        path.unlink()

    async def receive_file(self, remote_file_name: str, local_file_obj: typing.IO[bytes]) -> None:
        """The :meth:`.IOClientProto.receive_file` method implementation."""
        path = self.file_path(remote_file_name)
        with open(path, mode='rb') as f_remote:
            await self.__copy(f_remote, local_file_obj)

    async def file_size(self, remote_file_name: str) -> int:
        """The :meth:`.IOClientProto.file_size` method implementation."""
        path = pathlib.Path(self.session_path()) / remote_file_name
        return path.stat().st_size
