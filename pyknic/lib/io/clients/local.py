# -*- coding: utf-8 -*-
# pyknic/lib/io/clients/virtual_dir.py
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

import os
import pathlib
import typing

from pyknic.lib.registry import register_api
from pyknic.lib.uri import URI, URIQuery
from pyknic.lib.io import IOProducer, IOGenerator
from pyknic.lib.io.clients.virtual_dir import VirtualDirectoryClient
from pyknic.lib.io.clients.collection import __default_io_clients_registry__
from pyknic.lib.io.clients.proto import PartsUploaderProto
from pyknic.lib.io.clients.parts_uploader import BasePartsUploader
from pyknic.lib.verify import verify_value
from pyknic.lib.io.aio_wrapper import IOThrottler, cg


class _LocalFilePartsUploader(BasePartsUploader):

    def __init__(self, remote_file_name: str, part_size: int):
        BasePartsUploader.__init__(self, part_size)

        self.__part_size = part_size
        self.__remote_file_name = remote_file_name
        self.__opened_file: typing.Optional[typing.IO[bytes]] = None

    def __enter__(self) -> BasePartsUploader:
        assert(self.__opened_file is None)

        self.__opened_file = open(self.__remote_file_name, 'wb')
        return self

    def _upload_part(self, data: typing.Union[bytes, bytearray], part_number: int) -> None:
        assert(self.__opened_file)

        offset = part_number * self.__part_size
        self.__opened_file.seek(offset, os.SEEK_SET)
        self.__opened_file.write(data)

    def _finalize(self, exc_val: typing.Optional[BaseException] = None) -> None:
        assert(self.__opened_file)
        self.__opened_file.close()


@register_api(__default_io_clients_registry__, "file")
class LocalClient(VirtualDirectoryClient):
    """Local files implementation of :class:`.IOClientProto`."""

    def __init__(self, uri: URI) -> None:
        """Create a new client

        :param uri: URI with which this client should be created. If uri has the "path" attribute, then this path
        will be used as a start point
        """

        VirtualDirectoryClient.__init__(self, uri)

        self.__block_size = 4096

        if uri.query:
            query = URIQuery.parse(uri.query)

            if 'block_size' in query:
                block_size = query.single_parameter('block_size', int)
                if block_size < 4096:
                    raise ValueError(f'Block size must be greater than {4096} bytes, got {block_size}')
                self.__block_size = block_size

        if uri.path is not None:  # TODO: it is bad! Since it is relative!
            self.__change_directory(pathlib.PosixPath(uri.path))

    def current_directory(self) -> str:
        """The :meth:`.IOClientProto.current_directory` method implementation."""
        return str(self.session_path())

    def __change_directory(self, path: pathlib.PosixPath) -> pathlib.PosixPath:
        """Change current session directory to the specified one

        :param path: new session directory
        """
        if not path.is_absolute():
            path = self.session_path() / path

        if not pathlib.PosixPath(path).is_dir():
            raise NotADirectoryError(f'No such directory: {str(path)}')
        return self.session_path(pathlib.PosixPath(path))

    def change_directory(self, path: str) -> str:
        """The :meth:`.IOClientProto.change_directory` method implementation."""
        return str(self.__change_directory(pathlib.PosixPath(path)))

    def list_directory(self) -> typing.Tuple[str, ...]:
        """The :meth:`.IOClientProto.list_directory` method implementation."""
        return tuple(x.name for x in self.session_path().iterdir())

    def is_directory(self, directory_name: str) -> bool:
        """The :meth:`.IOClientProto.is_directory` method implementation."""
        path = pathlib.PosixPath(self.session_path()) / directory_name
        return path.is_dir()

    @verify_value(directory_name=lambda x: len(pathlib.PosixPath(x).parts) == 1)
    def make_directory(self, directory_name: str) -> None:
        """The :meth:`.IOClientProto.make_directory` method implementation."""
        path = pathlib.PosixPath(self.session_path()) / directory_name
        path.mkdir(exist_ok=False, parents=False)

    @verify_value(directory_name=lambda x: len(pathlib.PosixPath(x).parts) == 1)
    def remove_directory(self, directory_name: str) -> None:
        """The :meth:`.IOClientProto.remove_directory` method implementation."""
        path = pathlib.PosixPath(self.session_path()) / directory_name
        path.rmdir()

    @verify_value(remote_file_name=lambda x: len(pathlib.PosixPath(x).parts) == 1)
    def upload_file(self, remote_file_name: str, source: IOProducer) -> None:
        """The :meth:`.IOClientProto.upload_file` method implementation."""
        path = self.entry_path(remote_file_name)
        with open(str(path), mode='wb') as f_remote:
            cg(IOThrottler().sync_writer(source, f_remote))

    @verify_value(remote_file_name=lambda x: len(pathlib.PosixPath(x).parts) == 1)
    def append_file(self, remote_file_name: str, source: IOProducer) -> None:
        """The :meth:`.IOClientProto.append_file` method implementation."""

        path = self.entry_path(remote_file_name)
        with open(str(path), mode='ab') as f_remote:
            cg(IOThrottler().sync_writer(source, f_remote))

    @verify_value(remote_file_name=lambda x: len(pathlib.PosixPath(x).parts) == 1)
    def update_file(self, remote_file_name: str, source: IOProducer, offset: int = 0) -> None:
        """The :meth:`.IOClientProto.update_file` method implementation."""

        path = self.entry_path(remote_file_name)
        with open(str(path), mode='rb+') as f_remote:
            f_remote.seek(offset, os.SEEK_SET)
            cg(IOThrottler().sync_writer(source, f_remote))

    @verify_value(remote_file_name=lambda x: len(pathlib.PosixPath(x).parts) == 1)
    def truncate_file(self, remote_file_name: str, offset: int = 0) -> None:
        """The :meth:`.IOClientProto.truncate_file` method implementation."""
        path = self.entry_path(remote_file_name)
        with open(str(path), mode='ab') as f_remote:
            f_remote.truncate(offset)

    @verify_value(file_name=lambda x: len(pathlib.PosixPath(x).parts) == 1)
    def remove_file(self, file_name: str) -> None:
        """The :meth:`.IOClientProto.remove_file` method implementation."""
        path = self.entry_path(file_name)
        path.unlink()

    @verify_value(remote_file_name=lambda x: len(pathlib.PosixPath(x).parts) == 1)
    def receive_file(self, remote_file_name: str) -> IOGenerator:
        """The :meth:`.IOClientProto.receive_file` method implementation."""
        path = str(self.entry_path(remote_file_name))
        with open(path, mode='rb') as f_remote:
            yield from IOThrottler().sync_reader(f_remote)

    @verify_value(remote_file_name=lambda x: len(pathlib.PosixPath(x).parts) == 1, offset=lambda x: x >= 0)
    @verify_value(length=lambda x: x is None or x >= 0)
    def receive_file_with_offset(
        self, remote_file_name: str, offset: int = 0, length: typing.Optional[int] = None
    ) -> IOGenerator:
        """The :meth:`.IOClientProto.receive_file_with_offset` method implementation."""
        path = str(self.entry_path(remote_file_name))
        with open(path, mode='rb') as f_remote:
            f_remote.seek(offset, os.SEEK_SET)
            yield from IOThrottler().sync_reader(f_remote, read_size=length)

    @verify_value(remote_file_name=lambda x: len(pathlib.PosixPath(x).parts) == 1)
    def file_size(self, remote_file_name: str) -> int:
        """The :meth:`.IOClientProto.file_size` method implementation."""
        return self.entry_path(remote_file_name).stat().st_size

    def upload_by_part(self, remote_file_name: str, part_size: int) -> PartsUploaderProto:
        return _LocalFilePartsUploader(str(self.entry_path(remote_file_name)), part_size)
