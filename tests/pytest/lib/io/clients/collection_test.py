# -*- coding: utf-8 -*-

import pytest

from pyknic.lib.io.clients.collection import __default_io_clients_registry__, IOVirtualClient
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
