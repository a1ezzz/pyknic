# -*- coding: utf-8 -*-

import asyncio
import io
import pathlib

import pytest

from pyknic.lib.uri import URI

from pyknic.lib.io_clients.virtual_dir import VirtualDirectoryClient
from pyknic.lib.io_clients.local import LocalClient
from pyknic.lib.capability import iscapable
from pyknic.lib.io_clients.proto import IOClientProto

from fixtures.asyncio import pyknic_async_test


class TestLocalClient:

    # TODO: test scheme name!

    def test(self) -> None:
        client = LocalClient.create_client(URI.parse(''))
        assert(isinstance(client, VirtualDirectoryClient))
        assert(client.current_directory() == '/')

    def test_capabilities(self) -> None:
        client = LocalClient(URI.parse(''))
        assert(iscapable(client, IOClientProto.connect) is False)
        assert(iscapable(client, IOClientProto.disconnect) is False)
        assert(iscapable(client, IOClientProto.current_directory) is True)
        assert(iscapable(client, IOClientProto.change_directory) is True)
        assert(iscapable(client, IOClientProto.list_directory) is True)
        assert(iscapable(client, IOClientProto.make_directory) is True)
        assert(iscapable(client, IOClientProto.remove_directory) is True)
        assert(iscapable(client, IOClientProto.upload_file) is True)
        assert(iscapable(client, IOClientProto.remove_file) is True)
        assert(iscapable(client, IOClientProto.receive_file) is True)
        assert(iscapable(client, IOClientProto.file_size) is True)

    def test_path(self, tmp_path: pathlib.Path) -> None:
        client = LocalClient.create_client(URI.parse(''))
        assert(client.current_directory() == '/')

        client = LocalClient.create_client(URI.parse(str(tmp_path)))
        assert(client.current_directory() == str(tmp_path))

        with pytest.raises(NotADirectoryError):
            _ = LocalClient.create_client(URI.parse('/foo/bar/invalid/dir'))

    def test_block_size(self) -> None:
        # note: there is no way to check it for now, so lets check that there is no exception
        # TODO: check block_size in a real life!
        _ = LocalClient.create_client(URI.parse('?block_size=10000'))

    @pyknic_async_test
    async def test_change_directory(self, tmp_path: pathlib.Path, module_event_loop: asyncio.AbstractEventLoop) -> None:
        client = LocalClient.create_client(URI())
        assert(client.current_directory() == '/')

        assert(await client.change_directory(str(tmp_path)) == str(tmp_path))
        assert(client.current_directory() == str(tmp_path))

    @pyknic_async_test
    async def test_list_directory(self, tmp_path: pathlib.Path, module_event_loop: asyncio.AbstractEventLoop) -> None:
        dir_entries = ['dir1', 'dir2', 'dir3']
        file_entries = ['file1', 'file2', 'file3']

        # create complex structure
        for outer_dir_entry in dir_entries:
            outer_path = tmp_path / outer_dir_entry
            outer_path.mkdir()

            for inner_dir_entry in dir_entries:
                inner_path = tmp_path / outer_dir_entry / inner_dir_entry
                inner_path.mkdir()

        for file_name in file_entries:
            file_path = tmp_path / file_name
            file_path.touch()

            for dir_entry in dir_entries:
                file_path = tmp_path / dir_entry / file_name
                file_path.touch()

        sorted_entries = dir_entries + file_entries
        sorted_entries.sort()

        client = LocalClient.create_client(URI.parse(str(tmp_path)))
        listed_entries = list(await client.list_directory())
        listed_entries.sort()
        assert(sorted_entries == listed_entries)

    @pyknic_async_test
    async def test_make_remove_directory(
        self, tmp_path: pathlib.Path, module_event_loop: asyncio.AbstractEventLoop
    ) -> None:
        new_dir = tmp_path / 'new_dir'
        assert(not new_dir.exists())

        client = LocalClient.create_client(URI.parse(str(tmp_path)))
        await client.make_directory('new_dir')
        assert(new_dir.is_dir())

        await client.remove_directory('new_dir')
        assert(not new_dir.exists())

    @pyknic_async_test
    async def test_upload_receive_remove_file(
        self, tmp_path: pathlib.Path, module_event_loop: asyncio.AbstractEventLoop
    ) -> None:
        new_file = tmp_path / 'new_file'
        file_data = b'some test data'
        assert(not new_file.exists())

        client = LocalClient.create_client(URI.parse(str(tmp_path)))
        await client.upload_file('new_file', io.BytesIO(file_data))
        assert(new_file.is_file())

        fetched_data = open(str(new_file), 'rb').read()
        assert(fetched_data == file_data)

        target_file = io.BytesIO()
        await client.receive_file('new_file', target_file)
        target_file.seek(0)
        assert(target_file.read() == file_data)

        assert(await client.file_size('new_file') == len(file_data))

        assert(new_file.is_file())
        await client.remove_file('new_file')
        assert(not new_file.exists())
