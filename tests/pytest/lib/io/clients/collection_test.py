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

    @pytest.mark.parametrize('sftp_server', [3001], indirect=['sftp_server'])
    def test(self, sftp_server: sftp_fixture) -> None:
        uri = URI.parse(self.client_uri)
        client = IOVirtualClient.create_client(uri)
        client.connect()

        assert(client.uri() is uri)
