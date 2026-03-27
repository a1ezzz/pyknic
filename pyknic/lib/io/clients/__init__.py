# -*- coding: utf-8 -*-
# pyknic/lib/io/clients/__init__.py
#
# Copyright (C) 2025-2026 the pyknic authors and contributors
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

from pyknic.lib.io.clients.collection import IOVirtualClient
from pyknic.lib.io.clients.local import LocalClient
from pyknic.lib.io.clients.proto import DirectoryNotEmptyError, IOClientProto
from pyknic.lib.io.clients.s3 import S3Client
from pyknic.lib.io.clients.sftp import SFTPClient
from pyknic.lib.io.clients.virtual_dir import VirtualDirectoryClient

__all__ = [
    'IOVirtualClient',
    'LocalClient',
    'DirectoryNotEmptyError',
    'IOClientProto',
    'S3Client',
    'SFTPClient',
    'VirtualDirectoryClient'
]
