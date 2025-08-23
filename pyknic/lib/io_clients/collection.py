# -*- coding: utf-8 -*-
# pyknic/lib/io_clients/collection.py
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

import typing

from pyknic.lib.capability import iscapable
from pyknic.lib.registry import APIRegistry
from pyknic.lib.io_clients.proto import IOClientProto
from pyknic.lib.verify import verify_value
from pyknic.lib.uri import URI


__default_io_clients_registry__ = APIRegistry()


class IOVirtualClient(IOClientProto):

    @verify_value(uri=lambda x: x.scheme is not None)
    def __init__(self, uri: URI, registry: typing.Optional[APIRegistry] = None) -> None:
        IOClientProto.__init__(self)

        self.__uri = uri

        if registry is None:
            registry = __default_io_clients_registry__

        self.__client = registry.get(uri.scheme).create_client(uri)
        self.__init_capability('connect')
        self.__init_capability('disconnect')
        self.__init_capability('change_directory')
        self.__init_capability('list_directory')
        self.__init_capability('make_directory')
        self.__init_capability('remove_directory')
        self.__init_capability('upload_file')
        self.__init_capability('remove_file')
        self.__init_capability('receive_file')
        self.__init_capability('file_size')

    def __init_capability(self, method_name: str) -> None:
        cap = getattr(IOClientProto, method_name)
        if iscapable(self.__client, cap):
            self.append_capability(cap, getattr(self.__client, method_name))

    @classmethod
    def create_client(cls, uri: URI) -> 'IOClientProto':
        return cls(uri, registry=__default_io_clients_registry__)

    def uri(self) -> URI:
        return self.__uri
