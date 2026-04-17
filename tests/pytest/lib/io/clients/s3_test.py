# -*- coding: utf-8 -*-

import os
import pathlib
import uuid

import pytest

from pyknic.lib.uri import URI
from pyknic.lib.capability import iscapable
from pyknic.lib.io.clients.proto import IOClientProto, DirectoryNotEmptyError
from pyknic.lib.io.clients.s3 import S3Client


S3ConnectionEnvVar = "S3_TEST_URI"


# TODO: make it to run on concourse!
@pytest.mark.skipif(
    S3ConnectionEnvVar not in os.environ or os.environ[S3ConnectionEnvVar] == "",
    reason=f"Setup S3 connection URL with {S3ConnectionEnvVar} env var",
)
class TestS3Client:

    def test(self) -> None:
        client = S3Client(URI.parse(os.environ[S3ConnectionEnvVar]))
        client.connect()
        assert(client.session_path() == pathlib.PosixPath('/'))

        assert(iscapable(client, IOClientProto.connect) is True)
        assert(iscapable(client, IOClientProto.disconnect) is True)
        assert(iscapable(client, IOClientProto.current_directory) is True)
        assert(iscapable(client, IOClientProto.change_directory) is True)
        assert(iscapable(client, IOClientProto.list_directory) is True)
        assert(iscapable(client, IOClientProto.make_directory) is True)
        assert(iscapable(client, IOClientProto.remove_directory) is True)
        assert(iscapable(client, IOClientProto.upload_file) is True)
        assert(iscapable(client, IOClientProto.remove_file) is True)
        assert(iscapable(client, IOClientProto.receive_file) is True)
        assert(iscapable(client, IOClientProto.file_size) is True)

    def test_new_path(self) -> None:
        uri_obj = URI.parse(os.environ[S3ConnectionEnvVar])
        original_client = S3Client(uri_obj)
        original_client.connect()
        test_dir = f'pytest-directory-{uuid.uuid4()}'
        original_client.make_directory(test_dir)

        uri_obj.path = test_dir
        new_client = S3Client(uri_obj)
        new_client.connect()
        assert(new_client.session_path() == (pathlib.PosixPath('/') / test_dir))
        assert(new_client.list_directory() == tuple())

        original_client.remove_directory(test_dir)

    def test_dir(self) -> None:
        client = S3Client(URI.parse(os.environ[S3ConnectionEnvVar]))
        client.connect()

        test_dir = f'pytest-directory-{uuid.uuid4()}'
        client.make_directory(test_dir)

        with pytest.raises(FileExistsError):
            client.make_directory(test_dir)

        assert(test_dir in client.list_directory())
        client.change_directory(test_dir)
        assert(client.session_path() == pathlib.PosixPath(f'/{test_dir}/'))
        assert(test_dir not in client.list_directory())

        inner_dir1 = str(uuid.uuid4())
        inner_dir2 = str(uuid.uuid4())
        client.make_directory(inner_dir1)
        client.make_directory(inner_dir2)
        inner_dirs_result = client.list_directory()
        assert(test_dir not in inner_dirs_result)
        assert(inner_dir1 in inner_dirs_result)
        assert(inner_dir2 in inner_dirs_result)

        inner_inner_dir = str(uuid.uuid4())
        client.change_directory(inner_dir1)
        assert(client.session_path() == pathlib.PosixPath(f'/{test_dir}/{inner_dir1}'))
        client.make_directory(inner_inner_dir)
        assert(list(client.list_directory()) == [inner_inner_dir])
        client.remove_directory(inner_inner_dir)

        client.change_directory('..')
        assert(client.session_path() == pathlib.PosixPath(f'/{test_dir}'))
        assert(set(client.list_directory()) == {inner_dir1, inner_dir2})  # there is no inner_inner_dir

        client.change_directory('..')
        assert(client.session_path() == pathlib.PosixPath('/'))
        assert(client.current_directory() == '/')
        inner_dirs_result = client.list_directory()
        assert(test_dir in inner_dirs_result)
        assert(inner_dir1 not in inner_dirs_result)
        assert(inner_dir2 not in inner_dirs_result)

        with pytest.raises(DirectoryNotEmptyError):
            client.remove_directory(test_dir)

        client.change_directory(test_dir)
        client.remove_directory(inner_dir2)
        inner_dirs_result = client.list_directory()
        assert(inner_dir1 in inner_dirs_result)
        assert(inner_dir2 not in inner_dirs_result)

        client.remove_directory(inner_dir1)
        client.change_directory('/')
        client.remove_directory(test_dir)
        assert(test_dir not in client.list_directory())

    def test_file(self) -> None:
        client = S3Client(URI.parse(os.environ[S3ConnectionEnvVar]))
        client.connect()

        test_data = b'Test data'

        test_dir = f'pytest-directory-{uuid.uuid4()}'
        client.make_directory(test_dir)
        client.change_directory(test_dir)
        client.upload_file('remote-file', [test_data])

        assert(client.file_size('remote-file') == len(test_data))

        received_data = b''.join(client.receive_file('remote-file'))
        assert(received_data == test_data)

        assert(client.list_directory() == ('remote-file',))
        client.remove_file('remote-file')
        assert(client.list_directory() == tuple())

        client.change_directory('..')
        client.remove_directory(test_dir)

    def test_invalid_remove_dir(self) -> None:
        client = S3Client(URI.parse(os.environ[S3ConnectionEnvVar]))
        client.connect()

        test_dir = f'pytest-directory-{uuid.uuid4()}'
        client.make_directory(test_dir)
        client.change_directory(test_dir)

        data = b'Test data'
        client.upload_file('remote-file', [data])
        with pytest.raises(FileNotFoundError):
            client.remove_directory('remote-file')
        client.remove_file('remote-file')

        client.change_directory('..')
        client.remove_directory(test_dir)

    def test_receive_file_with_offset(self) -> None:
        client = S3Client(URI.parse(os.environ[S3ConnectionEnvVar]))
        client.connect()

        test_dir = f'pytest-directory-{uuid.uuid4()}'
        client.make_directory(test_dir)
        client.change_directory(test_dir)

        data = b'Test data'
        client.upload_file('remote-file', [data])

        received_data = b''.join(client.receive_file_with_offset('remote-file', offset=5))
        assert(received_data == b'data')

        client.remove_file('remote-file')
        client.change_directory('..')
        client.remove_directory(test_dir)

    def test_upload_by_part(self) -> None:
        client = S3Client(URI.parse(os.environ[S3ConnectionEnvVar]))
        client.connect()

        test_dir = f'pytest-directory-{uuid.uuid4()}'
        client.make_directory(test_dir)
        client.change_directory(test_dir)

        part_size = 5 * (1024 ** 2)

        with client.upload_by_part('new_file', part_size) as uploader:
            uploader.upload_part(b'b' * part_size, 1)
            uploader.upload_part(b'c' * 2, 2)
            uploader.upload_part(b'a' * part_size, 0)

        received_data = b''.join(client.receive_file('new_file'))
        assert(received_data == (b'a' * part_size + b'b' * part_size + b'c' * 2))

        client.remove_file('new_file')
        client.change_directory('..')
        client.remove_directory(test_dir)
