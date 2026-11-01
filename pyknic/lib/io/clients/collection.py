# -*- coding: utf-8 -*-
# pyknic/lib/io/clients/collection.py
#
# Copyright (C) 2017-2025 the pyknic authors and contributors
# <see AUTHORS file>
#
# This file is part of pyknic.
#
# pyknic is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# pyknic is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with pyknic.  If not, see <http://www.gnu.org/licenses/>.

import dataclasses
import enum
import pathlib
import types
import typing

from pyknic.lib.capability import iscapable
from pyknic.lib.registry import APIRegistry
from pyknic.lib.io.clients.proto import IOClientProto
from pyknic.lib.verify import verify_value
from pyknic.lib.uri import URI


__default_io_clients_registry__ = APIRegistry()


@enum.unique
class WalkEntryType(enum.Enum):
    """ Type of entry discovered during directory traversal
    """
    # TODO: add more types like symlinks when IOClientProto will have methods like "is_symlink"
    directory = enum.auto()
    general_file = enum.auto()


@dataclasses.dataclass
class WalkEntry:
    """ An entry discovered during directory traversal

    :param parent_directory: directory containing the entry (may be an absolute or relative path)
    :param entry_name: name of the entry
    :param entry_type: type of the entry (:class:`.WalkEntryType`)
    """
    parent_directory: str
    entry_name: str
    entry_type: WalkEntryType


class IOVirtualClient(IOClientProto):
    """ Virtual client that hides implementation
    """

    class ClientContext:
        """ Context manager for a client connect/disconnect routine
        """

        def __init__(self, client: IOClientProto):
            """ Create a new context

            :param client: client to connect/disconnect
            """
            self.__client = client

        def client(self) -> IOClientProto:
            """ Return client this context is connected to
            """
            return self.__client

        def walk(self, relative_path: bool = False) -> typing.Generator[WalkEntry, None, None]:
            """ Recursively traverse directory hierarchy starting from the client's current directory

            :param relative_path: whether to return parent directories relative to the start directory
            :return: generator yielding :class:`.WalkEntry` objects
            :raises ValueError: if client does not support required directory operations
            """

            if not iscapable(
                self.__client,
                IOClientProto.list_directory,
                IOClientProto.is_directory,
                IOClientProto.current_directory,
                IOClientProto.change_directory
            ):
                raise ValueError(
                    'The client does not support one feature at least: '
                    'list_directory, is_directory, current_directory and/or change_directory'
                )

            def entry_type(is_dir: bool) -> WalkEntryType:
                """ Determine WalkEntryType based on whether entry is a directory
                """
                return WalkEntryType.directory if is_dir else WalkEntryType.general_file

            def search_entry(parent_dir: str, sub_dir: str) -> str:
                """ Construct child entry path from parent directory and sub-directory name
                """
                return str(pathlib.PosixPath('/') / parent_dir / sub_dir)

            def parent_dir(abs_inner_path: str, start_path: str) -> str:
                """ Compute parent directory representation (relative or absolute)
                """
                if not relative_path:
                    return abs_inner_path

                if abs_inner_path == start_path:
                    return '.'

                if not start_path.endswith('/'):
                    start_path += '/'

                if not abs_inner_path.startswith(start_path):
                    raise RuntimeError(f'An inner path ({abs_inner_path}) is not from a parent path ({start_path})')

                return abs_inner_path[len(start_path):]

            start_directory = self.__client.current_directory()
            try:
                inner_entries = [start_directory]
                next_entries: list[str] = []

                while inner_entries:
                    next_entries = []

                    for i in inner_entries:

                        self.__client.change_directory(i)

                        for j in self.__client.list_directory():

                            is_dir = self.__client.is_directory(j)

                            yield WalkEntry(
                                parent_directory=parent_dir(i, start_directory),
                                entry_name=j,
                                entry_type=entry_type(is_dir)
                            )

                            if is_dir:
                                next_entries.append(search_entry(i, j))

                    inner_entries = next_entries

            finally:
                self.__client.change_directory(start_directory)

        def __enter__(self) -> typing.Self:
            """ Enter the context (client connects)
            """

            if iscapable(self.__client, IOClientProto.connect):
                self.__client.connect()
            return self

        def __exit__(
            self,
            exc_type: typing.Optional[typing.Type[BaseException]],
            exc_val: typing.Optional[BaseException],
            exc_tb: typing.Optional[types.TracebackType]
        ) -> None:
            """ Exit the context (client disconnects)
            """
            if iscapable(self.__client, IOClientProto.disconnect):
                self.__client.disconnect()

    class ClientNFileContext(ClientContext):
        """ Lightly enhanced :class:`.IOVirtualClient.ClientContext` that keeps a filename from URI
        """

        def __init__(self, client: IOClientProto, filename: str):
            """ Create a new context

            :param client: client to connect/disconnect
            :param filename: filename from URI
            """
            IOVirtualClient.ClientContext.__init__(self, client)
            self.__filename = filename

        def filename(self) -> str:
            """ Return filename that this context kept
            """
            return self.__filename

    @verify_value(uri=lambda x: x.scheme is not None)
    def __init__(self, uri: URI, registry: typing.Optional[APIRegistry] = None) -> None:
        """ Create a new client

        :param uri: URI that defines client
        :param registry: registry from which client will be derived (if not defined then the default one is used)
        """
        IOClientProto.__init__(self)

        self.__uri = uri

        if registry is None:
            registry = __default_io_clients_registry__

        self.__client = registry.get(uri.scheme).create_client(uri)
        self.__init_capability('connect')
        self.__init_capability('disconnect')
        self.__init_capability('current_directory')
        self.__init_capability('change_directory')
        self.__init_capability('list_directory')
        self.__init_capability('make_directory')
        self.__init_capability('remove_directory')
        self.__init_capability('is_directory')
        self.__init_capability('upload_file')
        self.__init_capability('append_file')
        self.__init_capability('update_file')
        self.__init_capability('truncate_file')
        self.__init_capability('remove_file')
        self.__init_capability('receive_file')
        self.__init_capability('receive_file_with_offset')
        self.__init_capability('file_size')
        self.__init_capability('upload_by_part')

    def __init_capability(self, method_name: str) -> None:
        """ Register capability on this client if underlying client supports it

        :param method_name: name of the capability method in :class:`.IOClientProto`
        """
        cap = getattr(IOClientProto, method_name)
        if iscapable(self.__client, cap):
            self.append_capability(cap, getattr(self.__client, method_name))

    @classmethod
    def create_client(cls, uri: URI) -> 'IOVirtualClient':
        """ Create a new client

        :param uri: URI that defines client
        """
        return cls(uri, registry=__default_io_clients_registry__)

    def uri(self) -> URI:
        """ Return URI with which client is created
        """
        return self.__uri

    def open(self) -> 'IOVirtualClient.ClientContext':
        """ Create a context which helps to connect and disconnect
        """
        return IOVirtualClient.ClientContext(self)

    @classmethod
    def create_n_open(cls, uri: URI) -> 'IOVirtualClient.ClientNFileContext':
        """ Split URI and return a context that connects/disconnects and keeps a filename from URI
        """
        file_name, modified_uri = uri.get_file()
        client = IOVirtualClient.create_client(modified_uri)

        return IOVirtualClient.ClientNFileContext(client, file_name)
