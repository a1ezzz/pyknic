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
from pyknic.lib.io.clients.virtual_dir import VirtualDirectoryClient, path_to_str
from pyknic.lib.io.clients.collection import __default_io_clients_registry__
from pyknic.lib.verify import verify_value


class _SFTPSyncImplementation:
    """This is a blocking (synchronous) SFTP client implementation.
    """

    @verify_value(uri=lambda x: x.hostname is not None)
    def __init__(self, uri: URI, vd_client: VirtualDirectoryClient):
        """Create a new SFTP client.

        :param uri: URI to connect with
        :param vd_client: original async client
        """

        self.__uri = uri
        self.__vd_client = vd_client
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
            return path_to_str(self.__vd_client.session_path())

        posix_path = pathlib.PosixPath(path)
        if not posix_path.is_absolute():
            posix_path = self.__vd_client.session_path() / posix_path

        try:
            self.__sftp_client.chdir(path_to_str(posix_path))
        finally:
            self.__sftp_client.chdir('/')

        normalized_path = pathlib.PosixPath(path_to_str(posix_path))
        return path_to_str(self.__vd_client.session_path(normalized_path))

    @verify_value(directory_name=lambda x: len(pathlib.PosixPath(x).parts) == 1)
    def make_directory(self, directory_name: str) -> None:
        """Synchronous implementation of the `.IOClientProto.make_directory` method
        """
        assert(self.__sftp_client is not None)
        new_dir_path = self.__vd_client.entry_path(directory_name)
        self.__sftp_client.mkdir(str(new_dir_path))

    @verify_value(directory_name=lambda x: len(pathlib.PosixPath(x).parts) == 1)
    def remove_directory(self, directory_name: str) -> None:
        """Synchronous implementation of the `.IOClientProto.remove_directory` method
        """
        assert(self.__sftp_client is not None)
        rm_dir_path = self.__vd_client.entry_path(directory_name)
        self.__sftp_client.rmdir(str(rm_dir_path))

    def list_directory(self) -> typing.Tuple[str, ...]:
        """Synchronous implementation of the `.IOClientProto.list_directory` method
        """
        assert(self.__sftp_client is not None)

        dir_to_list = path_to_str(self.__vd_client.session_path())
        return tuple(self.__sftp_client.listdir(dir_to_list))

    @verify_value(remote_file_name=lambda x: len(pathlib.PosixPath(x).parts) == 1)
    @verify_value(local_file_obj=lambda x: x.seekable())
    def upload_file(self, remote_file_name: str, local_file_obj: typing.IO[bytes]) -> None:
        """Synchronous implementation of the `.IOClientProto.upload_file` method
        """
        assert(self.__sftp_client is not None)

        local_file_obj.seek(0)
        data_length = local_file_obj.seek(0, os.SEEK_END)
        local_file_obj.seek(0)

        new_file_path = self.__vd_client.entry_path(remote_file_name)
        self.__sftp_client.putfo(local_file_obj, str(new_file_path), file_size=data_length)

    @verify_value(file_name=lambda x: len(pathlib.PosixPath(x).parts) == 1)
    def remove_file(self, file_name: str) -> None:
        """Synchronous implementation of the `.IOClientProto.remove_file` method
        """
        assert(self.__sftp_client is not None)
        rm_file_path = self.__vd_client.entry_path(file_name)
        self.__sftp_client.remove(str(rm_file_path))

    @verify_value(remote_file_name=lambda x: len(pathlib.PosixPath(x).parts) == 1)
    @verify_value(local_file_obj=lambda x: x.seekable())
    def receive_file(self, remote_file_name: str, local_file_obj: typing.IO[bytes]) -> None:
        """Synchronous implementation of the `.IOClientProto.receive_file` method
        """
        assert(self.__sftp_client is not None)

        local_file_obj.seek(0)
        local_file_obj.truncate()
        file_path = self.__vd_client.entry_path(remote_file_name)

        self.__sftp_client.getfo(str(file_path), local_file_obj)

    @verify_value(remote_file_name=lambda x: len(pathlib.PosixPath(x).parts) == 1)
    def file_size(self, remote_file_name: str) -> int:
        """Synchronous implementation of the `.IOClientProto.file_size` method
        """
        assert(self.__sftp_client is not None)

        file_path = self.__vd_client.entry_path(remote_file_name)
        stat = self.__sftp_client.stat(str(file_path))

        if stat.st_size is not None:
            return stat.st_size

        raise IOError('File size not available')


@register_api(__default_io_clients_registry__, "sftp")
class SFTPClient(VirtualDirectoryClient):
    """This is an asynced SFTP client.
    """

    def __init__(self, uri: URI) -> None:
        """Create a new SFTP client.

        :param uri: URI to connect with
        """
        VirtualDirectoryClient.__init__(self, uri)
        self.__i12n = _SFTPSyncImplementation(uri, self)

        self._wrap_capability(self.__i12n, 'connect')
        self._wrap_capability(self.__i12n, 'disconnect')
        self._wrap_capability(self.__i12n, 'change_directory')
        self._wrap_capability(self.__i12n, 'list_directory')
        self._wrap_capability(self.__i12n, 'make_directory')
        self._wrap_capability(self.__i12n, 'remove_directory')
        self._wrap_capability(self.__i12n, 'upload_file')
        self._wrap_capability(self.__i12n, 'remove_file')
        self._wrap_capability(self.__i12n, 'receive_file')
        self._wrap_capability(self.__i12n, 'file_size')

    def current_directory(self) -> str:
        """The :meth:`.IOClientProto.current_directory` method implementation."""
        return str(self.session_path())
