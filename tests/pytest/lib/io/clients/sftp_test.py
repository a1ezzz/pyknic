# -*- coding: utf-8 -*-

import pathlib
import uuid

import paramiko
import pytest

from pyknic.lib.capability import iscapable
from pyknic.lib.io.clients.proto import IOClientProto
from pyknic.lib.io.clients.sftp import SFTPClient
from pyknic.lib.uri import URI, URIQuery

from fixtures.sftp_server import sftp_fixture


@pytest.mark.parametrize('sftp_server', [3001], indirect=['sftp_server'])
class TestSFTPClient:

    client_uri = "sftp://foo:bar@127.0.0.1:3001/?host_key_auto_add="

    def test(self, sftp_server: sftp_fixture) -> None:
        client = SFTPClient(URI.parse(self.client_uri))

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

        client.disconnect()

    def test_unknown_host(self, sftp_server: sftp_fixture) -> None:
        uri = URI.parse(self.client_uri)
        uri.query = None
        client = SFTPClient(uri)

        with pytest.raises(ConnectionError):
            client.connect()

    def test_no_pass_error(self, sftp_server: sftp_fixture) -> None:
        uri = URI.parse(self.client_uri)
        uri.password = None

        with pytest.raises(ValueError):
            _ = SFTPClient(uri)

    def test_pkey(self, sftp_server: sftp_fixture, tmp_path: pathlib.Path) -> None:
        uri = URI.parse(self.client_uri)
        uri.password = None

        pk = paramiko.RSAKey.generate(1024)  # no need to be secure
        pk_file = tmp_path / 'user.key'
        pk.write_private_key_file(str(pk_file))

        uri_query = URIQuery.parse(uri.query)  # type: ignore[arg-type]
        uri_query.update('private_key_file', str(pk_file))
        uri.query = str(uri_query)

        client = SFTPClient(uri)
        client.connect()  # check that no exception is raised

    def test_new_path(self, sftp_server: sftp_fixture, tmp_path: pathlib.Path) -> None:
        sftp_server[1].base_dir = str(tmp_path)

        uri_obj = URI.parse(self.client_uri)
        original_client = SFTPClient(uri_obj)
        original_client.connect()
        test_dir = f'pytest-directory-{uuid.uuid4()}'
        original_client.make_directory(test_dir)

        uri_obj.path = test_dir
        new_client = SFTPClient(uri_obj)
        new_client.connect()
        assert(new_client.session_path() == (pathlib.PosixPath('/') / test_dir))
        assert(new_client.list_directory() == tuple())
        assert(new_client.change_directory('') == str(pathlib.PosixPath('/') / test_dir))

        original_client.remove_directory(test_dir)

    def test_dir(self, sftp_server: sftp_fixture, tmp_path: pathlib.Path) -> None:
        sftp_server[1].base_dir = str(tmp_path)

        client = SFTPClient(URI.parse(self.client_uri))
        client.connect()

        test_dir = f'pytest-directory-{uuid.uuid4()}'
        client.make_directory(test_dir)

        with pytest.raises(IOError):
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

        with pytest.raises(IOError):
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

    def test_file(self, sftp_server: sftp_fixture, tmp_path: pathlib.Path) -> None:
        sftp_server[1].base_dir = str(tmp_path)

        client = SFTPClient(URI.parse(self.client_uri))
        client.connect()

        # test_data = b'Test data' * (10 * (1024 ** 2))

        test_data = b'Test data' * (1 * (1024 ** 2))

        # test_data = b'Test data'

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

    def test_invalid_remove_dir(self, sftp_server: sftp_fixture, tmp_path: pathlib.Path) -> None:
        sftp_server[1].base_dir = str(tmp_path)

        client = SFTPClient(URI.parse(self.client_uri))
        client.connect()

        test_dir = f'pytest-directory-{uuid.uuid4()}'
        client.make_directory(test_dir)
        client.change_directory(test_dir)

        test_data = b'Test data'
        client.upload_file('remote-file', [test_data])
        with pytest.raises(IOError):
            client.remove_directory('remote-file')
        client.remove_file('remote-file')

        client.change_directory('..')
        client.remove_directory(test_dir)

    def test_append_file(self, sftp_server: sftp_fixture, tmp_path: pathlib.Path) -> None:
        sftp_server[1].base_dir = str(tmp_path)

        client = SFTPClient(URI.parse(self.client_uri))
        client.connect()

        test_dir = f'pytest-directory-{uuid.uuid4()}'
        client.make_directory(test_dir)
        client.change_directory(test_dir)

        test_data = b'Test data'
        client.upload_file('remote-file', [test_data])

        client.append_file('remote-file', [test_data])
        received_data = b''.join(client.receive_file('remote-file'))
        assert(received_data == (test_data + test_data))

    def test_update_file(self, sftp_server: sftp_fixture, tmp_path: pathlib.Path) -> None:
        sftp_server[1].base_dir = str(tmp_path)

        client = SFTPClient(URI.parse(self.client_uri))
        client.connect()

        test_dir = f'pytest-directory-{uuid.uuid4()}'
        client.make_directory(test_dir)
        client.change_directory(test_dir)

        test_data = b'Test data'
        client.upload_file('remote-file', [test_data])

        hi_data = b'hi'
        client.update_file('remote-file', [hi_data], offset=5)
        received_data = b''.join(client.receive_file('remote-file'))
        assert(received_data == b'Test hita')

        hello_data = b'hello'
        client.update_file('remote-file', [hello_data], offset=5)
        received_data = b''.join(client.receive_file('remote-file'))
        assert(received_data == b'Test hello')

    def test_truncate_file(self, sftp_server: sftp_fixture, tmp_path: pathlib.Path) -> None:
        sftp_server[1].base_dir = str(tmp_path)

        client = SFTPClient(URI.parse(self.client_uri))
        client.connect()

        test_dir = f'pytest-directory-{uuid.uuid4()}'
        client.make_directory(test_dir)
        client.change_directory(test_dir)

        test_data = b'Test data'
        client.upload_file('remote-file', [test_data])

        client.truncate_file('remote-file', 4)
        received_data = b''.join(client.receive_file('remote-file'))
        assert(received_data == b'Test')

        client.truncate_file('remote-file')
        received_data = b''.join(client.receive_file('remote-file'))
        assert(received_data == b'')

    def test_receive_file_with_offset(self, sftp_server: sftp_fixture, tmp_path: pathlib.Path) -> None:
        sftp_server[1].base_dir = str(tmp_path)

        client = SFTPClient(URI.parse(self.client_uri))
        client.connect()

        test_dir = f'pytest-directory-{uuid.uuid4()}'
        client.make_directory(test_dir)
        client.change_directory(test_dir)

        test_data = b'Test data'
        client.upload_file('remote-file', [test_data])

        received_data = b''.join(client.receive_file_with_offset('remote-file', 5))
        assert(received_data == b'data')

        received_data = b''.join(client.receive_file_with_offset('remote-file', 3))
        assert(received_data == b't data')

    def test_upload_by_part(self, sftp_server: sftp_fixture, tmp_path: pathlib.Path) -> None:
        sftp_server[1].base_dir = str(tmp_path)

        client = SFTPClient(URI.parse(self.client_uri))
        client.connect()

        with client.upload_by_part('new_file', 5) as uploader:
            uploader.upload_part(b'b' * 5, 1)
            uploader.upload_part(b'c' * 2, 2)
            uploader.upload_part(b'a' * 5, 0)

        received_data = b''.join(client.receive_file('new_file'))
        assert(received_data == (b'a' * 5 + b'b' * 5 + b'c' * 2))
