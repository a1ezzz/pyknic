# -*- coding: utf-8 -*-

import os
import pathlib

from pyknic.lib.uri import URI
from pyknic.lib.io_clients.virtual_dir import VirtualDirectoryClient


class TestVirtualDirectoryClient:

    def test_sanity(self) -> None:
        assert(os.sep == '/')  # just checks tests sanity

    def test(self) -> None:
        uri = URI()
        client = VirtualDirectoryClient.create_client(uri)
        assert(client.uri() is uri)
        assert(client.session_path() == pathlib.PosixPath('/'))

    def test_start_path(self) -> None:
        client = VirtualDirectoryClient(URI(), start_path=pathlib.PosixPath('/foo/bar'))
        assert(client.session_path() == pathlib.PosixPath('/foo/bar'))

    def test_join_path(self) -> None:
        client = VirtualDirectoryClient(URI())
        client.join_path('/foo/bar')
        assert(client.session_path() == pathlib.PosixPath('/foo/bar'))

        client = VirtualDirectoryClient(URI(), start_path=pathlib.PosixPath('/foo/bar/'))
        client.join_path('/foo/bar')
        assert(client.session_path() == pathlib.PosixPath('/foo/bar/foo/bar'))

    def test_session_path(self) -> None:
        client = VirtualDirectoryClient(URI())
        assert(client.session_path() == pathlib.PosixPath('/'))

        assert(client.session_path(pathlib.PosixPath('/foo/bar')) == pathlib.PosixPath('/foo/bar'))
        assert(client.session_path() == pathlib.PosixPath('/foo/bar'))

    def test_file_path(self) -> None:
        client = VirtualDirectoryClient(URI())
        assert(client.entry_path('foo') == pathlib.PosixPath('/foo'))

        client.session_path(pathlib.PosixPath('/foo/bar'))
        assert(client.entry_path('bar') == pathlib.PosixPath('/foo/bar/bar'))
