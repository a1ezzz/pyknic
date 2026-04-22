# -*- coding: utf-8 -*-
# pyknic/lib/io/clients/sftp.py
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

import os
import pathlib
import typing

import paramiko

from pyknic.lib.registry import register_api
from pyknic.lib.uri import URI, URIQuery
from pyknic.lib.io import IOProducer, IOGenerator
from pyknic.lib.io.clients.virtual_dir import VirtualDirectoryClient
from pyknic.lib.io.clients.collection import __default_io_clients_registry__
from pyknic.lib.io.clients.proto import PartsUploaderProto
from pyknic.lib.io.clients.parts_uploader import BasePartsUploader
from pyknic.lib.io.read_fo import ReadFileObject
from pyknic.lib.io.aio_wrapper import IOThrottler, cg
from pyknic.lib.verify import verify_value
from pyknic.lib.path import normalize_path


class _SFTPPartsUploader(BasePartsUploader):

    def __init__(self, sftp_client: paramiko.SFTPClient, remote_file_name: str, part_size: int):
        BasePartsUploader.__init__(self, part_size)

        self.__sftp_client = sftp_client
        self.__remote_file_name = remote_file_name
        self.__part_size = part_size

        self.__opened_file: typing.Optional[typing.IO[bytes]] = None

    def __enter__(self) -> BasePartsUploader:
        assert(self.__opened_file is None)

        self.__opened_file = self.__sftp_client.open(self.__remote_file_name, 'wb')  # type: ignore[assignment]
        return self

    def _upload_part(self, data: typing.Union[bytes, bytearray], part_number: int) -> None:
        assert(self.__opened_file)

        offset = part_number * self.__part_size
        self.__opened_file.seek(offset, os.SEEK_SET)
        self.__opened_file.write(data)

    def _finalize(self, exc_val: typing.Optional[BaseException] = None) -> None:
        assert(self.__opened_file)
        self.__opened_file.close()


@register_api(__default_io_clients_registry__, "sftp")
class SFTPClient(VirtualDirectoryClient):
    """ This is a SFTP client implementation.
    """

    @verify_value(uri=lambda x: x.hostname is not None)
    def __init__(self, uri: URI):
        """Create a new SFTP client.

        :param uri: URI to connect with
        """
        VirtualDirectoryClient.__init__(self, uri)

        self.__uri = uri
        self.__ssh_client: typing.Optional[paramiko.SSHClient] = None
        self.__sftp_client: typing.Optional[paramiko.SFTPClient] = None

        self.__host_key_auto_add = False
        self.__ssh_agent = False
        self.__private_key_file = None

        if self.__uri.query is not None:
            uri_query = URIQuery.parse(self.__uri.query)

            if 'host_key_auto_add' in uri_query:
                self.__host_key_auto_add = uri_query.single_parameter('host_key_auto_add', bool)

            if 'ssh_agent' in uri_query:
                self.__ssh_agent = uri_query.single_parameter('ssh_agent', bool)

            if 'private_key_file' in uri_query:
                self.__private_key_file = uri_query.single_parameter('private_key_file', str)

        if self.__uri.password is None and self.__private_key_file is None:
            raise ValueError('Password or private key file must be specified')

    def connect(self) -> None:
        """Synchronous implementation of the `.IOClientProto.connect` method
        """

        assert(self.__uri.hostname is not None)

        try:
            self.__ssh_client = paramiko.SSHClient()

            if self.__host_key_auto_add:
                self.__ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            self.__ssh_client.connect(
                hostname=self.__uri.hostname,
                port=(self.__uri.port if self.__uri.port is not None else 22),
                username=self.__uri.username,
                password=self.__uri.password,
                key_filename=self.__private_key_file,
                allow_agent=self.__ssh_agent
            )

            self.__sftp_client = self.__ssh_client.open_sftp()

            if self.__uri.path is not None:
                self.change_directory(self.__uri.path)
        except paramiko.ssh_exception.SSHException as e:
            self.disconnect()  # resets internal vars
            raise ConnectionError('Unable to connect') from e

    def disconnect(self) -> None:
        """Synchronous implementation of the `.IOClientProto.disconnect` method
        """
        if self.__sftp_client:
            self.__sftp_client.close()
            self.__sftp_client = None

        if self.__ssh_client:
            self.__ssh_client.close()
            self.__ssh_client = None

    def change_directory(self, path: str) -> str:
        """Synchronous implementation of the `.IOClientProto.change_directory` method
        """
        assert(self.__sftp_client is not None)

        if path in ('.', ''):
            return str(self.session_path())

        posix_path = pathlib.PosixPath(path)
        if not posix_path.is_absolute():
            posix_path = self.session_path() / posix_path

        normalized_path = normalize_path(posix_path)
        try:
            self.__sftp_client.chdir(str(normalized_path))
        finally:
            # there is no need for the real directory change
            self.__sftp_client.chdir('/')

        return str(self.session_path(normalized_path))

    @verify_value(directory_name=lambda x: len(pathlib.PosixPath(x).parts) == 1)
    def make_directory(self, directory_name: str) -> None:
        """Synchronous implementation of the `.IOClientProto.make_directory` method
        """
        assert(self.__sftp_client is not None)
        new_dir_path = self.entry_path(directory_name)
        self.__sftp_client.mkdir(str(new_dir_path))

    @verify_value(directory_name=lambda x: len(pathlib.PosixPath(x).parts) == 1)
    def remove_directory(self, directory_name: str) -> None:
        """Synchronous implementation of the `.IOClientProto.remove_directory` method
        """
        assert(self.__sftp_client is not None)
        rm_dir_path = self.entry_path(directory_name)
        self.__sftp_client.rmdir(str(rm_dir_path))

    def list_directory(self) -> typing.Tuple[str, ...]:
        """Synchronous implementation of the `.IOClientProto.list_directory` method
        """
        assert(self.__sftp_client is not None)

        dir_to_list = str(self.session_path())
        return tuple(self.__sftp_client.listdir(dir_to_list))

    @verify_value(remote_file_name=lambda x: len(pathlib.PosixPath(x).parts) == 1)
    def upload_file(self, remote_file_name: str, source: IOProducer) -> None:
        """Synchronous implementation of the `.IOClientProto.upload_file` method
        """
        assert(self.__sftp_client is not None)

        new_file_path = self.entry_path(remote_file_name)
        self.__sftp_client.putfo(ReadFileObject(source), str(new_file_path))  # type: ignore[arg-type]

    @verify_value(remote_file_name=lambda x: len(pathlib.PosixPath(x).parts) == 1)
    def append_file(self, remote_file_name: str, source: IOProducer) -> None:
        """The :meth:`.IOClientProto.append_file` method implementation."""
        assert(self.__sftp_client is not None)
        file_path = self.entry_path(remote_file_name)
        with self.__sftp_client.open(str(file_path), 'ab') as sftp_file:
            cg(IOThrottler().sync_writer(source, sftp_file))  # type: ignore[arg-type]

    @verify_value(remote_file_name=lambda x: len(pathlib.PosixPath(x).parts) == 1)
    def update_file(self, remote_file_name: str, source: IOProducer, offset: int = 0) -> None:
        """The :meth:`.IOClientProto.update_file` method implementation."""
        assert(self.__sftp_client is not None)
        file_path = self.entry_path(remote_file_name)
        with self.__sftp_client.open(str(file_path), 'rb+') as sftp_file:
            sftp_file.seek(offset, os.SEEK_SET)
            cg(IOThrottler().sync_writer(source, sftp_file))  # type: ignore[arg-type]

    @verify_value(remote_file_name=lambda x: len(pathlib.PosixPath(x).parts) == 1)
    def truncate_file(self, remote_file_name: str, offset: int = 0) -> None:
        """The :meth:`.IOClientProto.truncate_file` method implementation."""
        assert(self.__sftp_client is not None)
        path = self.entry_path(remote_file_name)
        with self.__sftp_client.open(str(path), mode='rb+') as f_remote:
            f_remote.truncate(offset)

    @verify_value(file_name=lambda x: len(pathlib.PosixPath(x).parts) == 1)
    def remove_file(self, file_name: str) -> None:
        """Synchronous implementation of the `.IOClientProto.remove_file` method
        """
        assert(self.__sftp_client is not None)
        rm_file_path = self.entry_path(file_name)
        self.__sftp_client.remove(str(rm_file_path))

    @verify_value(remote_file_name=lambda x: len(pathlib.PosixPath(x).parts) == 1)
    def receive_file(self, remote_file_name: str) -> IOGenerator:
        """Synchronous implementation of the `.IOClientProto.receive_file` method
        """
        assert(self.__sftp_client is not None)

        file_path = self.entry_path(remote_file_name)

        with self.__sftp_client.open(str(file_path), 'rb') as sftp_file:
            yield from IOThrottler().sync_reader(sftp_file)  # type: ignore[arg-type]

    @verify_value(remote_file_name=lambda x: len(pathlib.PosixPath(x).parts) == 1, offset=lambda x: x >= 0)
    @verify_value(length=lambda x: x is None or x >= 0)
    def receive_file_with_offset(
        self, remote_file_name: str, offset: int = 0, length: typing.Optional[int] = None
    ) -> IOGenerator:
        """The :meth:`.IOClientProto.receive_file_with_offset` method implementation."""
        assert(self.__sftp_client is not None)

        file_path = self.entry_path(remote_file_name)

        with self.__sftp_client.open(str(file_path), 'rb') as sftp_file:
            sftp_file.seek(offset, os.SEEK_SET)

            yield from IOThrottler().sync_reader(sftp_file, read_size=length)  # type: ignore[arg-type]

    @verify_value(remote_file_name=lambda x: len(pathlib.PosixPath(x).parts) == 1)
    def file_size(self, remote_file_name: str) -> int:
        """Synchronous implementation of the `.IOClientProto.file_size` method
        """
        assert(self.__sftp_client is not None)

        file_path = self.entry_path(remote_file_name)
        stat = self.__sftp_client.stat(str(file_path))

        if stat.st_size is not None:
            return stat.st_size

        raise IOError('File size not available')

    def upload_by_part(self, remote_file_name: str, part_size: int) -> PartsUploaderProto:
        assert(self.__sftp_client is not None)
        return _SFTPPartsUploader(self.__sftp_client, str(self.entry_path(remote_file_name)), part_size)
