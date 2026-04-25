# -*- coding: utf-8 -*-

import pathlib

import pytest

from pyknic.lib.uri import URI

from pyknic.lib.io.clients.virtual_dir import VirtualDirectoryClient
from pyknic.lib.io.clients.local import LocalClient
from pyknic.lib.capability import iscapable
from pyknic.lib.io.clients.proto import IOClientProto


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

    def test_change_directory(self, tmp_path: pathlib.Path) -> None:
        client = LocalClient.create_client(URI())
        assert(client.current_directory() == '/')

        assert(client.change_directory(str(tmp_path)) == str(tmp_path))
        assert(client.current_directory() == str(tmp_path))

    def test_is_directory(self, tmp_path: pathlib.Path) -> None:
        client = LocalClient.create_client(URI())
        assert(client.current_directory() == '/')

        client.change_directory(str(tmp_path))
        assert(client.is_directory('dir_name') is False)
        assert(client.is_directory('file_name') is False)

        client.upload_file('file_name', [b'some data'])
        client.make_directory('dir_name')
        assert(client.is_directory('dir_name') is True)
        assert(client.is_directory('file_name') is False)

    def test_list_directory(self, tmp_path: pathlib.Path) -> None:
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
        listed_entries = list(client.list_directory())
        listed_entries.sort()
        assert(sorted_entries == listed_entries)

    def test_make_remove_directory(self, tmp_path: pathlib.Path) -> None:
        new_dir = tmp_path / 'new_dir'
        assert(not new_dir.exists())

        client = LocalClient.create_client(URI.parse(str(tmp_path)))
        client.make_directory('new_dir')
        assert(new_dir.is_dir())

        client.remove_directory('new_dir')
        assert(not new_dir.exists())

    def test_upload_receive_remove_file(self, tmp_path: pathlib.Path) -> None:
        new_file = tmp_path / 'new_file'
        file_data = b'some test data'
        assert(not new_file.exists())

        client = LocalClient.create_client(URI.parse(str(tmp_path)))
        client.upload_file('new_file', [file_data])
        assert(new_file.is_file())

        fetched_data = open(str(new_file), 'rb').read()
        assert(fetched_data == file_data)

        assert(b''.join(client.receive_file('new_file')) == file_data)

        assert(client.file_size('new_file') == len(file_data))

        assert(new_file.is_file())
        client.remove_file('new_file')
        assert(not new_file.exists())

    def test_append_file(self, tmp_path: pathlib.Path) -> None:
        new_file = tmp_path / 'new_file'
        file_data = b'some test data'
        assert(not new_file.exists())

        client = LocalClient.create_client(URI.parse(str(tmp_path)))
        client.upload_file('new_file', [file_data])

        client.append_file('new_file', [file_data])
        received_data = b''.join(client.receive_file('new_file'))
        assert(received_data == (file_data + file_data))

    def test_update_file(self, tmp_path: pathlib.Path) -> None:
        new_file = tmp_path / 'new_file'
        file_data = b'some test data'
        assert(not new_file.exists())

        client = LocalClient.create_client(URI.parse(str(tmp_path)))
        client.upload_file('new_file', [file_data])

        hello_data = b'hello'
        client.update_file('new_file', [hello_data], offset=5)
        received_data = b''.join(client.receive_file('new_file'))
        assert(received_data == b'some hellodata')

        hello_data = b'hello-hello'
        client.update_file('new_file', [hello_data], offset=5)
        received_data = b''.join(client.receive_file('new_file'))
        assert(received_data == b'some hello-hello')

    def test_truncate_file(self, tmp_path: pathlib.Path) -> None:
        new_file = tmp_path / 'new_file'
        file_data = b'some test data'
        assert(not new_file.exists())

        client = LocalClient.create_client(URI.parse(str(tmp_path)))
        client.upload_file('new_file', [file_data])

        client.truncate_file('new_file', 4)
        received_data = b''.join(client.receive_file('new_file'))
        assert(received_data == b'some')

        client.truncate_file('new_file')
        received_data = b''.join(client.receive_file('new_file'))
        assert(received_data == b'')

    def test_receive_file_with_offset(self, tmp_path: pathlib.Path) -> None:
        new_file = tmp_path / 'new_file'
        file_data = b'some test data'
        assert(not new_file.exists())

        client = LocalClient.create_client(URI.parse(str(tmp_path)))
        client.upload_file('new_file', [file_data])

        received_data = b''.join(client.receive_file_with_offset('new_file', offset=5))
        assert(received_data == b'test data')

        received_data = b''.join(client.receive_file_with_offset('new_file', offset=5, length=4))
        assert(received_data == b'test')

    def test_upload_by_part(self, tmp_path: pathlib.Path) -> None:

        client = LocalClient.create_client(URI.parse(str(tmp_path)))

        with client.upload_by_part('new_file', 5) as uploader:
            uploader.upload_part(b'b' * 5, 1)
            uploader.upload_part(b'c' * 2, 2)
            uploader.upload_part(b'a' * 5, 0)

        received_data = b''.join(client.receive_file('new_file'))
        assert(received_data == (b'a' * 5 + b'b' * 5 + b'c' * 2))
