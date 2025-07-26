# -*- coding: utf-8 -*-

import asyncio
import io
import os
import pathlib
import uuid

import pytest

from pyknic.lib.uri import URI
from pyknic.lib.capability import iscapable
from pyknic.lib.io_clients.proto import IOClientProto, DirectoryNotEmptyError
from pyknic.lib.io_clients.s3 import S3Client

from fixtures.asyncio import pyknic_async_test


S3ConnectionEnvVar = "S3_TEST_URI"


@pytest.mark.skipif(
    S3ConnectionEnvVar not in os.environ or os.environ[S3ConnectionEnvVar] == "",
    reason=f"Setup S3 connection URL with {S3ConnectionEnvVar} env var",
)
class TestS3Client:

    @pyknic_async_test
    async def test(self, module_event_loop: asyncio.AbstractEventLoop) -> None:
        client = S3Client(URI.parse(os.environ[S3ConnectionEnvVar]))
        await client.connect()
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

    @pyknic_async_test
    async def test_new_path(self, module_event_loop: asyncio.AbstractEventLoop) -> None:
        uri_obj = URI.parse(os.environ[S3ConnectionEnvVar])
        original_client = S3Client(uri_obj)
        await original_client.connect()
        test_dir = f'pytest-directory-{uuid.uuid4()}'
        await original_client.make_directory(test_dir)

        uri_obj.path = test_dir
        new_client = S3Client(uri_obj)
        await new_client.connect()
        assert(new_client.session_path() == (pathlib.PosixPath('/') / test_dir))
        assert(await new_client.list_directory() == tuple())

        await original_client.remove_directory(test_dir)

    @pyknic_async_test
    async def test_dir(self, module_event_loop: asyncio.AbstractEventLoop) -> None:
        client = S3Client(URI.parse(os.environ[S3ConnectionEnvVar]))
        await client.connect()

        test_dir = f'pytest-directory-{uuid.uuid4()}'
        await client.make_directory(test_dir)

        with pytest.raises(FileExistsError):
            await client.make_directory(test_dir)

        assert(test_dir in await client.list_directory())
        await client.change_directory(test_dir)
        assert(client.session_path() == pathlib.PosixPath(f'/{test_dir}/'))
        assert(test_dir not in await client.list_directory())

        inner_dir1 = str(uuid.uuid4())
        inner_dir2 = str(uuid.uuid4())
        await client.make_directory(inner_dir1)
        await client.make_directory(inner_dir2)
        inner_dirs_result = await client.list_directory()
        assert(test_dir not in inner_dirs_result)
        assert(inner_dir1 in inner_dirs_result)
        assert(inner_dir2 in inner_dirs_result)

        inner_inner_dir = str(uuid.uuid4())
        await client.change_directory(inner_dir1)
        assert(client.session_path() == pathlib.PosixPath(f'/{test_dir}/{inner_dir1}'))
        await client.make_directory(inner_inner_dir)
        assert(list(await client.list_directory()) == [inner_inner_dir])
        await client.remove_directory(inner_inner_dir)

        await client.change_directory('..')
        assert(client.session_path() == pathlib.PosixPath(f'/{test_dir}'))
        assert(set(await client.list_directory()) == {inner_dir1, inner_dir2})  # there is no inner_inner_dir

        await client.change_directory('..')
        assert(client.session_path() == pathlib.PosixPath('/'))
        assert(client.current_directory() == '/')
        inner_dirs_result = await client.list_directory()
        assert(test_dir in inner_dirs_result)
        assert(inner_dir1 not in inner_dirs_result)
        assert(inner_dir2 not in inner_dirs_result)

        with pytest.raises(DirectoryNotEmptyError):
            await client.remove_directory(test_dir)

        await client.change_directory(test_dir)
        await client.remove_directory(inner_dir2)
        inner_dirs_result = await client.list_directory()
        assert(inner_dir1 in inner_dirs_result)
        assert(inner_dir2 not in inner_dirs_result)

        await client.remove_directory(inner_dir1)
        await client.change_directory('/')
        await client.remove_directory(test_dir)
        assert(test_dir not in await client.list_directory())

    @pyknic_async_test
    async def test_file(self, module_event_loop: asyncio.AbstractEventLoop) -> None:
        client = S3Client(URI.parse(os.environ[S3ConnectionEnvVar]))
        await client.connect()

        test_data = b'Test data'
        test_file_data = io.BytesIO(test_data)

        test_dir = f'pytest-directory-{uuid.uuid4()}'
        await client.make_directory(test_dir)
        await client.change_directory(test_dir)
        await client.upload_file('remote-file', test_file_data)

        assert(await client.file_size('remote-file') == len(test_data))

        received_data = io.BytesIO()
        await client.receive_file('remote-file', received_data)
        received_data.seek(0)
        assert(received_data.read() == test_data)

        assert(await client.list_directory() == ('remote-file',))
        await client.remove_file('remote-file')
        assert(await client.list_directory() == tuple())

        await client.change_directory('..')
        await client.remove_directory(test_dir)

    @pyknic_async_test
    async def test_invalid_remove_dir(self, module_event_loop: asyncio.AbstractEventLoop) -> None:
        client = S3Client(URI.parse(os.environ[S3ConnectionEnvVar]))
        await client.connect()

        test_dir = f'pytest-directory-{uuid.uuid4()}'
        await client.make_directory(test_dir)
        await client.change_directory(test_dir)

        await client.upload_file('remote-file', io.BytesIO(b'Test data'))
        with pytest.raises(FileNotFoundError):
            await client.remove_directory('remote-file')
        await client.remove_file('remote-file')

        await client.change_directory('..')
        await client.remove_directory(test_dir)
