# -*- coding: utf-8 -*-
# pyknic/lib/io/clients/s3.py
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

import pathlib
import re
import typing

import boto3.session
import botocore.client
import botocore.exceptions

from pyknic.lib.registry import register_api
from pyknic.lib.uri import URI, URIQuery
from pyknic.lib.io import IOGenerator, IOProducer
from pyknic.lib.io.clients.proto import DirectoryNotEmptyError
from pyknic.lib.io.clients.virtual_dir import VirtualDirectoryClient
from pyknic.lib.io.clients.collection import __default_io_clients_registry__
from pyknic.lib.io.clients.proto import PartsUploaderProto
from pyknic.lib.io.clients.parts_uploader import BasePartsUploader
from pyknic.lib.io.read_fo import ReadFileObject
from pyknic.lib.io.aio_wrapper import IOThrottler
from pyknic.lib.verify import verify_value
from pyknic.lib.path import normalize_path


class _S3PartsUploader(BasePartsUploader):

    __minimal_part_size__ = 5 * (1024 ** 2)  # minimum part size

    @verify_value(part_size=lambda x: x >= _S3PartsUploader.__minimal_part_size__)
    def __init__(self, client: botocore.client.BaseClient, bucket: str, remote_file_name: str, part_size: int):
        BasePartsUploader.__init__(self, part_size)

        self.__client = client
        self.__bucket = bucket
        self.__remote_file_name = remote_file_name
        self.__part_size = part_size

        self.__mp_request = None
        self.__parts_info: typing.List[typing.Dict[str, typing.Any]] = list()

    def __enter__(self) -> BasePartsUploader:
        assert(self.__mp_request is None)

        self.__mp_request = self.__client.create_multipart_upload(
            Bucket=self.__bucket,
            Key=self.__remote_file_name
        )

        return self

    def _upload_part(self, data: typing.Union[bytes, bytearray], part_number: int) -> None:
        assert(self.__mp_request)

        upload_request = self.__client.upload_part(
            Bucket=self.__bucket,
            Key=self.__remote_file_name,
            UploadId=self.__mp_request["UploadId"],
            PartNumber=(part_number + 1),
            Body=data
        )

        self.__parts_info.append(
            {'PartNumber': part_number + 1, 'ETag': upload_request["ETag"]}
        )

    def _finalize(self, exc_val: typing.Optional[BaseException] = None) -> None:
        if exc_val is not None and self.__mp_request is not None:
            self.__client.abort_multipart_upload(
                Bucket=self.__bucket,
                Key=self.__remote_file_name,
                UploadId=self.__mp_request["UploadId"],
            )
        else:
            assert(self.__mp_request)

            self.__client.complete_multipart_upload(
                Bucket=self.__bucket,
                Key=self.__remote_file_name,
                UploadId=self.__mp_request["UploadId"],
                MultipartUpload={'Parts': self.__parts_info}
            )


@register_api(__default_io_clients_registry__, "s3s")
@register_api(__default_io_clients_registry__, "s3")
class S3Client(VirtualDirectoryClient):
    """ This is a S3 client implementation.
    """

    __list_objects_re__ = re.compile('^([^/]+)/?.*')

    @verify_value(uri=lambda x: x.hostname is not None)
    @verify_value(uri=lambda x: x.query is not None)
    def __init__(self, uri: URI):
        """Create a new client

        :param uri: URI with which this client should be created. If uri has the "path" attribute, then this path
        will be used as a start point
        """
        VirtualDirectoryClient.__init__(self, uri)

        self.__uri = uri
        self.__session: typing.Optional[boto3.session.Session] = None
        self.__client: typing.Optional[botocore.client.BaseClient] = None
        self.__block_size = 4096

        if self.__uri.query is None:
            raise ValueError('Query parameters for S3 Client must be provided')

        self.__uri_query = URIQuery.parse(self.__uri.query)
        self.__bucket_name = self.__uri_query.single_parameter('bucket_name', str)

        if 'block_size' in self.__uri_query:
            block_size = self.__uri_query.single_parameter('block_size', int)
            if block_size < 4096:
                raise ValueError(f'Block size must be greater than {4096} bytes, got {block_size}')
            self.__block_size = block_size

    def connect(self) -> None:

        connection_uri = URI(
            scheme=('https' if self.__uri.scheme != 's3' else 'http'),
            username=self.__uri.username,
            password=self.__uri.password,
            hostname=self.__uri.hostname,
            port=self.__uri.port,
        )

        secure = self.__uri.scheme != 's3'

        self.__session = boto3.session.Session(  # type: ignore[no-untyped-call]
            aws_access_key_id=self.__uri_query.single_parameter('access_key', str),
            aws_secret_access_key=self.__uri_query.single_parameter('secret_key', str),

        )

        self.__client = self.__session.client(  # type: ignore[no-untyped-call]
            service_name='s3',
            endpoint_url=str(connection_uri),
            use_ssl=secure,
        )

        try:
            buckets_response = self.__client.list_buckets()

            if self.__bucket_name not in (x["Name"] for x in buckets_response["Buckets"]):  # mypy issue
                raise ConnectionError(
                    f'There is no such bucket "{self.__bucket_name}", buckets that are available:'
                )
        except botocore.exceptions.ClientError as e:
            raise ConnectionError('Connection error') from e

        if self.__uri.path is not None:
            self.change_directory(self.__uri.path)

    def disconnect(self) -> None:
        assert(self.__client is not None)

        self.__client.close()  # type: ignore[no-untyped-call]
        self.__client = None
        self.__session = None

    @verify_value(object_path=lambda x: x.is_absolute())
    def __has_inner_objects(self, object_path: pathlib.PosixPath) -> bool:
        try:
            next(self.__list_generator(object_path))
            return True
        except StopIteration:
            pass

        return False

    @verify_value(object_path=lambda x: x.is_absolute())
    def __has_entry(self, object_path: pathlib.PosixPath, directory_entry: bool = True) -> bool:
        assert(self.__client is not None)

        object_path_str = self.relative_path(object_path)
        if not object_path:
            return False

        try:
            if directory_entry:
                object_path_str += '/'

            self.__client.head_object(Bucket=self.__bucket_name, Key=object_path_str)

            return True
        except botocore.exceptions.ClientError:
            pass

        return False

    def change_directory(self, path: str) -> str:
        if path in ('.', ''):
            return str(self.session_path())

        posix_path = pathlib.PosixPath(path)
        if not posix_path.is_absolute():
            posix_path = self.session_path() / posix_path

        posix_path = normalize_path(posix_path)

        if str(posix_path) != '/':
            if not self.__has_entry(posix_path, True):
                raise NotADirectoryError(f'There is no such directory: {path}')

        return str(self.session_path(posix_path))

    @verify_value(directory_name=lambda x: len(pathlib.PosixPath(x).parts) == 1)
    def make_directory(self, directory_name: str) -> None:
        assert (self.__client is not None)

        new_dir_path = self.entry_path(directory_name)

        if self.__has_entry(new_dir_path, False) or self.__has_entry(new_dir_path, True):
            raise FileExistsError(f'Object {str(new_dir_path)} already exists')

        self.__client.put_object(
            Bucket=self.__bucket_name,
            Key=self.relative_path(new_dir_path) + '/',
            Body=b'',
        )

    @verify_value(directory_name=lambda x: len(pathlib.PosixPath(x).parts) == 1)
    def remove_directory(self, directory_name: str) -> None:
        assert (self.__client is not None)

        rm_dir_path = self.entry_path(directory_name)

        if not self.__has_entry(rm_dir_path, True):
            raise FileNotFoundError(f'There is no such directory {str(rm_dir_path)}')

        if self.__has_inner_objects(rm_dir_path):
            raise DirectoryNotEmptyError(f'There is inner object(s) inside a directory {rm_dir_path}')

        self.__client.delete_object(Bucket=self.__bucket_name, Key=(self.relative_path(rm_dir_path) + '/'))

    @verify_value(object_path=lambda x: x.is_absolute())
    def __list_generator(self, list_path: pathlib.PosixPath) -> typing.Generator[str, None, None]:
        assert (self.__client is not None)

        request_path_str = self.relative_path(list_path)
        if request_path_str == '.':
            request_path_str = ''

        path = self.relative_path(list_path)
        if path:
            path += '/'

        list_request = self.__client.list_objects_v2(Bucket=self.__bucket_name, Prefix=str(path))

        all_entries = (x["Key"] for x in list_request.get("Contents", []))

        def map_items(m: str) -> str:
            relative_name = m[len(request_path_str):].lstrip('/')
            re_search = self.__list_objects_re__.search(relative_name)
            return re_search.group(1).rstrip('/') if re_search else ''

        relative_names_entries = map(map_items, all_entries)
        filtered_entries = filter(lambda y: y != '', relative_names_entries)

        for x in filtered_entries:
            next_item = pathlib.PosixPath(x).parts[-1].rstrip('/')
            if next_item != request_path_str:
                yield next_item.rstrip('/')

    def list_directory(self) -> typing.Tuple[str, ...]:
        return tuple(self.__list_generator(self.session_path()))

    def is_directory(self, directory_name: str) -> bool:
        dir_path = self.entry_path(directory_name)
        return self.__has_entry(dir_path, True)

    @verify_value(remote_file_name=lambda x: len(pathlib.PosixPath(x).parts) == 1)
    def upload_file(self, remote_file_name: str, source: IOProducer) -> None:
        assert (self.__client is not None)

        new_file_path = self.entry_path(remote_file_name)

        if self.__has_entry(new_file_path, False) or self.__has_entry(new_file_path, True):
            raise FileExistsError(f'Object {str(new_file_path)} already exists')

        self.__client.upload_fileobj(
            Fileobj=ReadFileObject(source),
            Bucket=self.__bucket_name,
            Key=self.relative_path(new_file_path),
        )

    @verify_value(file_name=lambda x: len(pathlib.PosixPath(x).parts) == 1)
    def remove_file(self, file_name: str) -> None:
        assert (self.__client is not None)

        rm_file_path = self.entry_path(file_name)

        entry = self.__has_entry(rm_file_path, False)
        if entry is None:
            raise FileNotFoundError(f'There is no such file {str(rm_file_path)}')

        self.__client.delete_object(Bucket=self.__bucket_name, Key=self.relative_path(rm_file_path))

    @verify_value(remote_file_name=lambda x: len(pathlib.PosixPath(x).parts) == 1)
    def receive_file(self, remote_file_name: str) -> IOGenerator:
        assert(self.__client is not None)

        file_path = self.entry_path(remote_file_name)

        if not self.__has_entry(file_path, False):
            raise FileNotFoundError(f'There is no such file {str(file_path)}')

        get_request = self.__client.get_object(
            Bucket=self.__bucket_name, Key=self.relative_path(file_path)
        )

        yield from IOThrottler().sync_reader(get_request["Body"])

    @verify_value(remote_file_name=lambda x: len(pathlib.PosixPath(x).parts) == 1, offset=lambda x: x >= 0)
    @verify_value(length=lambda x: x is None or x >= 0)
    def receive_file_with_offset(
        self, remote_file_name: str, offset: int = 0, length: typing.Optional[int] = None
    ) -> IOGenerator:
        """The :meth:`.IOClientProto.receive_file_with_offset` method implementation."""

        assert (self.__client is not None)

        file_path = self.entry_path(remote_file_name)

        if not self.__has_entry(file_path, False):
            raise FileNotFoundError(f'There is no such file {str(file_path)}')

        file_size = self.file_size(remote_file_name)

        get_request = self.__client.get_object(
            Bucket=self.__bucket_name, Key=self.relative_path(file_path), Range=f'bytes={offset}-{file_size}'
        )

        yield from IOThrottler().sync_reader(get_request["Body"], read_size=length)

    @verify_value(remote_file_name=lambda x: len(pathlib.PosixPath(x).parts) == 1)
    def file_size(self, remote_file_name: str) -> int:
        assert (self.__client is not None)

        file_path = self.entry_path(remote_file_name)

        if not self.__has_entry(file_path, False):
            raise FileNotFoundError(f'There is no such file {str(file_path)}')

        head_request = self.__client.head_object(Bucket=self.__bucket_name, Key=self.relative_path(file_path))
        return int(head_request["ContentLength"])

    def upload_by_part(self, remote_file_name: str, part_size: int) -> PartsUploaderProto:
        assert(self.__client is not None)

        file_path = self.entry_path(remote_file_name)

        if self.__has_entry(file_path, False) or self.__has_entry(file_path, True):
            raise FileExistsError(f'Object {str(file_path)} already exists')

        return _S3PartsUploader(self.__client, self.__bucket_name, self.relative_path(file_path), part_size)

    @staticmethod
    @verify_value(path=lambda x: x.is_absolute())
    def relative_path(path: pathlib.PosixPath) -> str:
        """ Return relative path
        """
        # TODO: test it!

        result = str(path.relative_to(pathlib.PosixPath('/')))
        return '' if result == '.' else result
