# -*- coding: utf-8 -*-
# pyknic/lib/io_clients/s3.py
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

import io
import functools
import os
import pathlib
import typing

import minio

from pyknic.lib.uri import URI, URIQuery
from pyknic.lib.io_clients.proto import ClientConnectionError, IOClientProto
from pyknic.lib.io_clients.virtual_dir import VirtualDirectoryClient, path_to_str
from pyknic.lib.verify import verify_value
from pyknic.lib.tasks.aio_wrapper import AsyncWrapper

# TODO: register client with registry!


class _S3ClientSyncImplementation:

    # TODO: check result of .__client methods calls!

    @verify_value(uri=lambda x: x.hostname is not None)
    @verify_value(uri=lambda x: x.query is not None)
    def __init__(self, uri: URI, vd_client: VirtualDirectoryClient):

        self.__uri = uri
        self.__vd_client = vd_client
        self.__client = None

        self.__uri_query = URIQuery.parse(self.__uri.query)
        self.__bucket_name = self.__uri_query.single_parameter('bucket_name', str)

    def connect(self):

        connection_uri = URI(
            username=self.__uri.username,
            password=self.__uri.password,
            hostname=self.__uri.hostname,
            port=self.__uri.port,
        )

        secure = self.__uri.scheme != 'http'

        self.__client = minio.Minio(
            str(connection_uri),
            secure=secure,
            access_key=self.__uri_query.single_parameter('access_key', str),
            secret_key=self.__uri_query.single_parameter('secret_key', str),
        )

        available_buckets = self.__client.list_buckets()
        if self.__bucket_name not in available_buckets:
            raise ClientConnectionError(
                f'There is no such bucket "{self.__bucket_name}", buckets that are available:'
            )

        if self.__uri.path is not None:
            self.change_directory(self.__uri.path)

    def disconnect(self) -> None:
        # TODO: check if there is ".close" method
        self.__client = None

    @verify_value(object_path=lambda x: x.is_absolute())
    def __list_directory(self, object_path: pathlib.PosixPath):
        # NOTE: list_objects returns all objects with full paths
        path = path_to_str(object_path, relative_path=True)
        if path:
            path += '/'

        return self.__client.list_objects(self.__bucket_name, prefix=path)

    @verify_value(object_path=lambda x: x.is_absolute())
    def __get_entry(self, object_path: pathlib.PosixPath, dir_suffix: bool = False):
        object_path = path_to_str(object_path, relative_path=True)
        if not object_path:
            return None

        if dir_suffix:
            object_path += '/'

        try:
            return self.__client.get_object(self.__bucket_name, object_path)
        except minio.error.S3Error:
            pass

    def change_directory(self, path: str) -> str:
        if path in ('.', ''):
            return path_to_str(self.__vd_client.session_path())

        posix_path = pathlib.PosixPath(path)
        if not posix_path.is_absolute():
            posix_path = self.__vd_client.session_path() / posix_path
            posix_path = posix_path.resolve(strict=False)

        if path_to_str(posix_path) != '/':
            # TODO: check that "posix_path" is a directory! NOT A FILE!
            entry = self.__get_entry(posix_path, True)
            if entry is None:
                raise NotADirectoryError(f'There is no such directory: {path}')

        return path_to_str(self.__vd_client.session_path(posix_path))

    @verify_value(directory_name=lambda x: len(pathlib.PosixPath(x).parts) == 1)
    def make_directory(self, directory_name: str) -> None:
        new_dir_path = self.__vd_client.entry_path(directory_name)
        invalid_names = (directory_name, directory_name + '/')

        for entry in (x.object_name for x in self.__list_directory(self.__vd_client.session_path())):
            if entry in invalid_names:
                raise FileExistsError(f'Object {path_to_str(new_dir_path)} already exists')

        self.__client.put_object(
            self.__bucket_name, path_to_str(new_dir_path, relative_path=True) + '/', io.BytesIO(b''), 0
        )

    @verify_value(directory_name=lambda x: len(pathlib.PosixPath(x).parts) == 1)
    def remove_directory(self, directory_name: str) -> None:
        rm_dir_path = self.__vd_client.entry_path(directory_name)

        # TODO: check that "directory_name" is a directory! NOT A FILE!
        entry = self.__get_entry(rm_dir_path, True)
        if entry is None:
            raise FileNotFoundError(f'There is no such directory {path_to_str(rm_dir_path)}')

        errors = self.__client.remove_object(self.__bucket_name, path_to_str(rm_dir_path, relative_path=True) + '/')

    def list_directory(self) -> typing.Tuple[str, ...]:
        current_path_str = path_to_str(self.__vd_client.session_path(), relative_path=True)
        if current_path_str == '.':
            current_path_str = ''

        def map_items(x):
            return x.object_name[len(current_path_str):].rstrip('/').lstrip('/')

        def list_generator():

            all_entries = self.__list_directory(self.__vd_client.session_path())
            relative_names_entries = map(map_items, all_entries)
            filtered_entries = filter(lambda y: y != '', relative_names_entries)

            for x in filtered_entries:
                next_item = pathlib.PosixPath(x).parts[-1].rstrip('/')
                if next_item != current_path_str:
                    yield next_item.rstrip('/')

        return tuple(list_generator())

    @verify_value(remote_file_name=lambda x: len(pathlib.PosixPath(x).parts) == 1)
    def upload_file(self, remote_file_name: str, local_file_obj: typing.IO[bytes]) -> None:
        local_file_obj.seek(0)
        data_length = local_file_obj.seek(0, os.SEEK_END)
        local_file_obj.seek(0)

        # TODO: check that there is a file already!

        new_file_path = self.__vd_client.entry_path(remote_file_name)
        self.__client.put_object(
            self.__bucket_name, path_to_str(new_file_path, relative_path=True), local_file_obj, data_length
        )

    @verify_value(file_name=lambda x: len(pathlib.PosixPath(x).parts) == 1)
    def remove_file(self, file_name: str) -> None:
        rm_file_path = self.__vd_client.entry_path(file_name)

        # TODO: check that "directory_name" is a FILE! NOT A DIRECTORY!
        entry = self.__get_entry(rm_file_path)
        if entry is None:
            raise FileNotFoundError(f'There is no such file {path_to_str(rm_file_path)}')

        errors = self.__client.remove_object(self.__bucket_name, path_to_str(rm_file_path, relative_path=True))

    @verify_value(remote_file_name=lambda x: len(pathlib.PosixPath(x).parts) == 1)
    def receive_file(self, remote_file_name: str, local_file_obj: typing.IO[bytes]) -> None:
        local_file_obj.seek(0)

        file_path = self.__vd_client.entry_path(remote_file_name)

        # TODO: check that we will download a file!

        http_request = self.__client.get_object(
            self.__bucket_name, path_to_str(file_path, relative_path=True)
        )

        data = http_request.read(1024)  # TODO: customizable batch size!
        while data != b'':
            local_file_obj.write(data)
            data = http_request.read(1024)

    @verify_value(remote_file_name=lambda x: len(pathlib.PosixPath(x).parts) == 1)
    def file_size(self, remote_file_name: str) -> int:

        file_path = self.__vd_client.entry_path(remote_file_name)

        # TODO: check that file_path is a file

        result = self.__client.stat_object(
            self.__bucket_name, path_to_str(file_path, relative_path=True)
        )

        return result.size


class S3Client(VirtualDirectoryClient):

    def __init__(self, uri: URI) -> None:
        """Create a new client

        :param uri: URI with which this client should be created. If uri has the "path" attribute, then this path
        will be used as a start point
        """

        VirtualDirectoryClient.__init__(self, uri)
        self.__i12n = _S3ClientSyncImplementation(uri, self)

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

    def _wrap_capability(self, implementation, method_name):
        # TODO: to some basic class implementation?!

        async def wrapper_fn(*args, **kwargs) -> typing.Any:
            method_fn = getattr(implementation, method_name)
            caller = await AsyncWrapper.create(functools.partial(method_fn, *args, **kwargs))
            return await caller()

        self.append_capability(getattr(IOClientProto, method_name), wrapper_fn)

    def current_directory(self) -> str:
        """The :meth:`.IOClientProto.current_directory` method implementation."""
        return str(self.session_path())
