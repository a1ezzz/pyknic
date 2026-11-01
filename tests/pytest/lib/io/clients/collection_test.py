# -*- coding: utf-8 -*-

import pathlib
import pytest

from pyknic.lib.io.clients.collection import __default_io_clients_registry__, IOVirtualClient, WalkEntry
from pyknic.lib.io.clients.collection import WalkEntryType
from pyknic.lib.io.clients.proto import IOClientProto
from pyknic.lib.uri import URI

from fixtures.sftp_server import sftp_fixture


def test_collection() -> None:
    available_clients = list(__default_io_clients_registry__.ids())
    available_clients.sort()  # type: ignore[call-arg]

    assert(available_clients == ['file', 's3', 's3s', 'sftp'])


class TestIOVirtualClient:

    client_uri = "sftp://foo:bar@127.0.0.1:3001/?host_key_auto_add="
    client_uri_w_file = "sftp://foo:bar@127.0.0.1:3001/remote-file?host_key_auto_add="

    @pytest.mark.parametrize('sftp_server', [3001], indirect=['sftp_server'])
    def test(self, sftp_server: sftp_fixture) -> None:
        uri = URI.parse(self.client_uri)
        client = IOVirtualClient.create_client(uri)
        client.connect()

        assert(client.uri() is uri)

    @pytest.mark.parametrize('sftp_server', [3001], indirect=['sftp_server'])
    def test_context(self, sftp_server: sftp_fixture) -> None:

        uri = URI.parse(self.client_uri)
        client = IOVirtualClient.create_client(uri)
        with client.open() as c:
            assert(c.client() is client)

            file_data = b'some data'
            client.upload_file('remote-file', [file_data])

    @pytest.mark.parametrize('sftp_server', [3001], indirect=['sftp_server'])
    def test_create_n_open(self, sftp_server: sftp_fixture) -> None:

        uri = URI.parse(self.client_uri_w_file)
        with IOVirtualClient.create_n_open(uri) as c:
            assert(isinstance(c.client(), IOVirtualClient))
            assert(c.filename() == 'remote-file')

    def test_walk(self, tmp_path: pathlib.Path) -> None:
        file1 = tmp_path / 'file1.txt'
        file1.touch()

        dir1 = tmp_path / 'dir1'
        dir1.mkdir()
        file2 = dir1 / 'file2.txt'
        file2.touch()

        dir2 = dir1 / 'dir2'
        dir2.mkdir()
        file3 = dir2 / 'file3.txt'
        file3.touch()

        client = IOVirtualClient.create_client(URI.parse(f'file://{tmp_path}'))
        with client.open() as c:
            start_dir = client.current_directory()
            entries = list(c.walk(relative_path=False))
            assert(client.current_directory() == start_dir)

            entries.sort(key=lambda e: (e.parent_directory, e.entry_name))
            expected = [
                WalkEntry(str(tmp_path), 'dir1', WalkEntryType.directory),
                WalkEntry(str(tmp_path), 'file1.txt', WalkEntryType.general_file),
                WalkEntry(str(dir1), 'dir2', WalkEntryType.directory),
                WalkEntry(str(dir1), 'file2.txt', WalkEntryType.general_file),
                WalkEntry(str(dir2), 'file3.txt', WalkEntryType.general_file),
            ]
            expected.sort(key=lambda e: (e.parent_directory, e.entry_name))
            assert(entries == expected)

    def test_walk_relative(self, tmp_path: pathlib.Path) -> None:
        file1 = tmp_path / 'file1.txt'
        file1.touch()

        dir1 = tmp_path / 'dir1'
        dir1.mkdir()
        file2 = dir1 / 'file2.txt'
        file2.touch()

        dir2 = dir1 / 'dir2'
        dir2.mkdir()
        file3 = dir2 / 'file3.txt'
        file3.touch()

        client = IOVirtualClient.create_client(URI.parse(f'file://{tmp_path}'))
        with client.open() as c:
            start_dir = client.current_directory()
            entries = list(c.walk(relative_path=True))
            assert(client.current_directory() == start_dir)

            entries.sort(key=lambda e: (e.parent_directory, e.entry_name))
            expected = [
                WalkEntry('.', 'dir1', WalkEntryType.directory),
                WalkEntry('.', 'file1.txt', WalkEntryType.general_file),
                WalkEntry('dir1', 'dir2', WalkEntryType.directory),
                WalkEntry('dir1', 'file2.txt', WalkEntryType.general_file),
                WalkEntry('dir1/dir2', 'file3.txt', WalkEntryType.general_file),
            ]
            expected.sort(key=lambda e: (e.parent_directory, e.entry_name))
            assert(entries == expected)

    def test_walk_empty_directory(self, tmp_path: pathlib.Path) -> None:
        client = IOVirtualClient.create_client(URI.parse(f'file://{tmp_path}'))
        with client.open() as c:
            start_dir = client.current_directory()
            entries = list(c.walk())
            assert(entries == [])
            assert(client.current_directory() == start_dir)

    def test_walk_restore_on_exception(self, tmp_path: pathlib.Path) -> None:
        dir1 = tmp_path / 'dir1'
        dir1.mkdir()
        (dir1 / 'file.txt').touch()

        client = IOVirtualClient.create_client(URI.parse(f'file://{tmp_path}'))
        with client.open() as c:
            start_dir = client.current_directory()
            with pytest.raises(RuntimeError, match='stop iteration'):
                for entry in c.walk():
                    if entry.entry_type == WalkEntryType.directory:
                        raise RuntimeError('stop iteration')

            assert(client.current_directory() == start_dir)

    def test_walk_not_capable(self) -> None:
        class IncompleteClient(IOClientProto):
            @classmethod
            def create_client(cls, uri: URI) -> 'IOClientProto':
                return cls()

            def uri(self) -> URI:
                return URI()

        ctx = IOVirtualClient.ClientContext(IncompleteClient())
        with pytest.raises(ValueError, match='The client does not support one feature at least'):
            list(ctx.walk())

    @pytest.mark.parametrize('sftp_server', [3001], indirect=['sftp_server'])
    def test_walk_sftp(self, sftp_server: sftp_fixture, tmp_path: pathlib.Path) -> None:
        sftp_server[1].base_dir = str(tmp_path)
        uri = URI.parse(self.client_uri)
        client = IOVirtualClient.create_client(uri)
        with client.open() as c:
            client.make_directory('sftp_dir')
            client.upload_file('sftp_file', [b'123'])
            client.change_directory('sftp_dir')
            client.upload_file('inner_file', [b'456'])
            client.change_directory('/')

            entries = list(c.walk(relative_path=True))
            entries.sort(key=lambda e: (e.parent_directory, e.entry_name))

            expected = [
                WalkEntry('.', 'sftp_dir', WalkEntryType.directory),
                WalkEntry('.', 'sftp_file', WalkEntryType.general_file),
                WalkEntry('sftp_dir', 'inner_file', WalkEntryType.general_file),
            ]
            expected.sort(key=lambda e: (e.parent_directory, e.entry_name))
            assert(entries == expected)
