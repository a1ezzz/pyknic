# -*- coding: utf-8 -*-

import os
import pathlib

import pytest

from pyknic.lib.uri import URI
from pyknic.lib.io_clients.virtual_dir import VirtualDirectoryClient


class TestVirtualDirectoryClient:

    def test_sanity(self) -> None:
        assert(os.sep == '/')  # just checks tests sanity

    def test(self) -> None:
        uri = URI()
        client = VirtualDirectoryClient.create_client(uri)
        assert(client.uri() is uri)
        assert(client.session_path() == '/')

    def test_start_path(self) -> None:
        client = VirtualDirectoryClient(URI(), start_path=pathlib.Path('/foo/bar'))
        assert(client.session_path() == '/foo/bar')

    def test_directory_sep(self) -> None:
        client = VirtualDirectoryClient(URI(), directory_sep='\\')
        assert(client.session_path() == '\\')

        client = VirtualDirectoryClient(URI(), start_path=pathlib.Path('/foo/bar'), directory_sep='\\')
        assert(client.session_path() == '\\foo\\bar')

        with pytest.raises(ValueError):
            _ = VirtualDirectoryClient(URI(), directory_sep='#')

    def test_join_path(self) -> None:
        client = VirtualDirectoryClient(URI())
        client.join_path('/foo/bar')
        assert(client.session_path() == '/foo/bar')

        client = VirtualDirectoryClient(URI(), start_path=pathlib.Path('/foo/bar/'))
        client.join_path('/foo/bar')
        assert(client.session_path() == '/foo/bar/foo/bar')

    def test_session_path(self) -> None:
        client = VirtualDirectoryClient(URI())
        assert(client.session_path() == '/')

        assert(client.session_path(pathlib.Path('/foo/bar')) == '/foo/bar')
        assert(client.session_path() == '/foo/bar')

    def test_file_path(self) -> None:
        client = VirtualDirectoryClient(URI())
        assert(client.file_path('/foo') == '/foo')

        client.session_path(pathlib.Path('/foo/bar'))
        assert(client.file_path('bar') == '/foo/bar/bar')
        assert(client.file_path('/bar') == '/foo/bar/bar')
        assert(client.file_path('/bar/foo') == '/foo/bar/bar/foo')
