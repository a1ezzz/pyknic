# -*- coding: utf-8 -*-
# pyknic/lib/io_clients/proto.py
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

import os
import typing
from abc import abstractmethod

from pyknic.lib.capability import CapabilitiesHolder, capability
from pyknic.lib.uri import URI


class ClientConnectionError(Exception):
	"""An exception is raised when connection attempt is failed."""
	pass


class IOClientProto(CapabilitiesHolder):
	""" Base class for network clients. This class implements :class:`.WSchemeHandler` to handle connections
	encoded as URI and :class:`.WCapabilitiesHolder` to use capabilities as different client requests
	"""

	# TODO: add basic async with usage, that will create, connect and disconnect client at the end

	@classmethod
	@abstractmethod
	def create_client(cls, uri: URI) -> 'IOClientProto':
		raise NotImplementedError('This method is abstract')

	@capability
	async def connect(self) -> None:
		"""Connect to a source specified in URI."""
		raise NotImplementedError('This method is abstract')

	@capability
	async def disconnect(self) -> None:
		"""Disconnect from a source."""
		raise NotImplementedError('This method is abstract')

	@abstractmethod
	def uri(self) -> URI:
		"""Return URI with which this client was created."""
		raise NotImplementedError('This method is abstract')

	# noinspection PyMethodMayBeStatic
	def directory_sep(self) -> str:
		"""Return symbol that is used by this client as a directory separator. If a path starts with that
		symbol then it treats as an absolute path by default."""
		return os.sep

	@capability
	def current_directory(self) -> str:
		"""Return current session directory"""
		raise NotImplementedError('This method is abstract')

	@capability
	async def change_directory(self, path: str) -> str:
		"""Change current session directory to the specified one. If the path begins with directory separator
		then it may be treated as an absolute path.

		:return: new session directory
		"""
		raise NotImplementedError('This method is abstract')

	@capability
	async def list_directory(self) -> typing.Tuple[str, ...]:
		"""List current session directory."""
		raise NotImplementedError('This method is abstract')

	@capability
	async def make_directory(self, directory_name: str) -> None:
		"""Create directory. A directory is created in a current session directory. And a name must not
		contain a directory separator.

		:param directory_name: directory name to create
		"""
		raise NotImplementedError('This method is abstract')

	@capability
	async def remove_directory(self, directory_name: str) -> None:
		"""Remove directory. A directory is removed from a current session directory. And a name must not
		contain a directory separator.

		:param directory_name: directory name to remove
		"""
		raise NotImplementedError('This method is abstract')

	@capability
	async def upload_file(self, remote_file_name: str, local_file_obj: typing.IO[bytes]) -> None:
		"""Upload file. File will be uploaded to a current session directory. A name must not contain
		a directory separator

		:param remote_file_name: target file name
		:param local_file_obj: source object to upload
		"""
		raise NotImplementedError('This method is abstract')

	@capability
	async def remove_file(self, file_name: str) -> None:
		"""Remove file. File will be removed from a current session directory. A name must not contain
		a directory separator

		:param file_name: file to remove
		"""
		raise NotImplementedError('This method is abstract')

	@capability
	async def receive_file(self, remote_file_name: str, local_file_obj: typing.IO[bytes]) -> None:
		"""Fetch/download a file. A remote file name must not contain a directory separator

		:param remote_file_name: file to fetch
		:param local_file_obj: a file where data should be stored
		"""
		raise NotImplementedError('This method is abstract')

	@capability
	async def file_size(self, remote_file_name: str) -> int:
		"""Return size of file in bytes.

		:param remote_file_name: file to check
		"""
		raise NotImplementedError('This method is abstract')
