# -*- coding: utf-8 -*-
# pyknic/lib/io/clients/proto.py
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

import pathlib
import types
import typing

from abc import abstractmethod, ABCMeta

from pyknic.lib.io import IOGenerator, IOProducer
from pyknic.lib.capability import CapabilitiesHolder, capability
from pyknic.lib.uri import URI

from pyknic.lib.verify import verify_value


class DirectoryNotEmptyError(Exception):
    """An exception is raised when there is a request to delete a directory which has inner files."""
    pass


class InvalidPartSize(Exception):
    """ This exception is raised when a size of a part does not match initialization value"""
    pass


class NonSequentialPartNumbers(Exception):
    """ There were missing parts when part uploading is finalized. Or there were multiple parts with the same number
    """
    pass


class PartsUploaderProto(metaclass=ABCMeta):
    """ This is a part of the :meth:`.IOClientProto.upload_by_part` capability. This class should implement a logic
    that will upload a single file split by parts. Every part (except a last one) must be the same size as it was
    defined in the :meth:`.IOClientProto.upload_by_part` method. Parts are numbered from zero
    """

    @abstractmethod
    def __enter__(self) -> 'PartsUploaderProto':
        """ Start and initialize this uploader
        """

        raise NotImplementedError('This method is abstract')

    @abstractmethod
    def __exit__(
        self,
        exc_type: typing.Optional[typing.Type[BaseException]],
        exc_val: typing.Optional[BaseException],
        exc_tb: typing.Optional[types.TracebackType]
    ) -> None:
        """ Finalize this uploader and combine all uploaded parts
        """
        raise NotImplementedError('This method is abstract')

    def upload_part(self, data: bytes, part_number: int) -> None:
        """ Upload data

        :param data: data to upload. For not last past a size of a data must be the same size as it was
        defined in the :meth:`.IOClientProto.upload_by_part` method
        :param part_number: part number (sequential number that starts from zero)
        """
        raise NotImplementedError('This method is abstract')


class IOClientProto(CapabilitiesHolder):
    """ Base class for network clients. This class implements :class:`.WSchemeHandler` to handle connections
    encoded as URI and :class:`.WCapabilitiesHolder` to use capabilities as different client requests
    """

    # TODO: add signals that will notify about copying progress

    @classmethod
    @abstractmethod
    def create_client(cls, uri: URI) -> 'IOClientProto':
        raise NotImplementedError('This method is abstract')

    @capability
    def connect(self) -> None:
        """Connect to a source specified in URI."""
        raise NotImplementedError('This method is abstract')

    @capability
    def disconnect(self) -> None:
        """Disconnect from a source."""
        raise NotImplementedError('This method is abstract')

    @abstractmethod
    def uri(self) -> URI:
        """Return URI with which this client was created."""
        raise NotImplementedError('This method is abstract')

    @capability
    def current_directory(self) -> str:
        """Return current session directory"""
        raise NotImplementedError('This method is abstract')

    @capability
    def change_directory(self, path: str) -> str:
        """Change current session directory to the specified one. If the path begins with directory separator
        then it may be treated as an absolute path.

        :return: new session directory
        """
        raise NotImplementedError('This method is abstract')

    @capability
    def list_directory(self) -> typing.Tuple[str, ...]:
        """List current session directory."""
        raise NotImplementedError('This method is abstract')

    @capability
    @verify_value(directory_name=lambda x: len(pathlib.PosixPath(x).parts) == 1)
    def make_directory(self, directory_name: str) -> None:
        """Create directory. A directory is created in a current session directory. And a name must not
        contain a directory separator.

        :param directory_name: directory name to create
        """
        raise NotImplementedError('This method is abstract')

    @capability
    @verify_value(directory_name=lambda x: len(pathlib.PosixPath(x).parts) == 1)
    def remove_directory(self, directory_name: str) -> None:
        """Remove directory. A directory is removed from a current session directory. And a name must not
        contain a directory separator.

        :param directory_name: directory name to remove
        """
        raise NotImplementedError('This method is abstract')

    @capability
    @verify_value(remote_file_name=lambda x: len(pathlib.PosixPath(x).parts) == 1)
    def upload_file(self, remote_file_name: str, source: IOProducer) -> None:
        """Upload file. File will be uploaded to a current session directory. A name must not contain
        a directory separator

        :param remote_file_name: target file name
        :param source: data to upload
        """
        raise NotImplementedError('This method is abstract')

    @capability
    @verify_value(remote_file_name=lambda x: len(pathlib.PosixPath(x).parts) == 1)
    def append_file(self, remote_file_name: str, source: IOProducer) -> None:
        """Append data a file. Updated file will be changed in a current session directory. A name must not contain
        a directory separator

        :param remote_file_name: target file name to update
        :param source: data to upload
        """
        raise NotImplementedError('This method is abstract')

    @capability
    @verify_value(remote_file_name=lambda x: len(pathlib.PosixPath(x).parts) == 1)
    def update_file(self, remote_file_name: str, source: IOProducer, offset: int = 0) -> None:
        """Update a file (replace and or update date from the offset). Updated file will be changed in a current
        session directory. A name must not contain a directory separator

        :param remote_file_name: target file name to update
        :param source: data to upload
        :param offset: offset to change a file from
        """
        raise NotImplementedError('This method is abstract')

    @capability
    @verify_value(remote_file_name=lambda x: len(pathlib.PosixPath(x).parts) == 1)
    def truncate_file(self, remote_file_name: str, offset: int = 0) -> None:
        """ Truncate a remote file. Truncated file will be changed in a current session directory. A name must not
        contain a directory separator

        :param remote_file_name: target file name to update
        :param offset: offset from a start to keep a data
        """
        raise NotImplementedError('This method is abstract')

    @capability
    @verify_value(file_name=lambda x: len(pathlib.PosixPath(x).parts) == 1)
    def remove_file(self, file_name: str) -> None:
        """Remove file. File will be removed from a current session directory. A name must not contain
        a directory separator

        :param file_name: file to remove
        """
        raise NotImplementedError('This method is abstract')

    @capability
    @verify_value(remote_file_name=lambda x: len(pathlib.PosixPath(x).parts) == 1)
    def receive_file(self, remote_file_name: str) -> IOGenerator:
        """Fetch/download a file. A remote file name must not contain a directory separator

        :param remote_file_name: file to fetch
        """
        raise NotImplementedError('This method is abstract')

    @capability
    @verify_value(remote_file_name=lambda x: len(pathlib.PosixPath(x).parts) == 1, offset=lambda x: x >= 0)
    @verify_value(length=lambda x: x is None or x >= 0)
    def receive_file_with_offset(
        self, remote_file_name: str, offset: int = 0, length: typing.Optional[int] = None
    ) -> IOGenerator:
        """Fetch/download a file. A remote file name must not contain a directory separator

        :param remote_file_name: file to fetch
        :param offset: offset to start from
        :param length: length of data to fetch. The length if data is mandatory if defined
        """
        raise NotImplementedError('This method is abstract')

    @capability
    @verify_value(remote_file_name=lambda x: len(pathlib.PosixPath(x).parts) == 1)
    def file_size(self, remote_file_name: str) -> int:
        """Return size of file in bytes.

        :param remote_file_name: file to check
        """
        raise NotImplementedError('This method is abstract')

    @capability
    def upload_by_part(self, remote_file_name: str, part_size: int) -> PartsUploaderProto:
        """ Return context manager that will help to upload data part by part (chunk by chunk)

        :param remote_file_name: file to upload
        :param part_size: exact number of bytes each part must have
        """
        raise NotImplementedError('This method is abstract')
