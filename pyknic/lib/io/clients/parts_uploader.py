# -*- coding: utf-8 -*-
# pyknic/lib/io/clients/parts_uploader.py
#
# Copyright (C) 2026 the pyknic authors and contributors
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

import types
import typing

from abc import ABCMeta, abstractmethod

from pyknic.lib.io.clients.proto import PartsUploaderProto, NonSequentialPartNumbers, InvalidPartSize


class BasePartsUploader(PartsUploaderProto, metaclass=ABCMeta):
    """ This is a basic implementation of the :class:`PartsUploaderProto`. It does some checks routine
    """

    def __init__(self, part_size: int):
        """ Create an uploader

        :param part_size: a static size of following parts
        """

        PartsUploaderProto.__init__(self)

        self.__part_size = part_size
        self.__uploaded_parts: typing.Set[int] = set()
        self.__final_part: typing.Optional[int] = None

    @abstractmethod
    def _finalize(self, exc_val: typing.Optional[BaseException] = None) -> None:
        """ Finalize uploading
        """
        raise NotImplementedError('This method is abstract')

    @abstractmethod
    def _upload_part(self, data: typing.Union[bytes, bytearray], part_number: int) -> None:
        """ Upload a single part

        :param data: data to upload
        :param part_number: number of the part to be uploaded
        """
        raise NotImplementedError('This method is abstract')

    def __exit__(
        self,
        exc_type: typing.Optional[typing.Type[BaseException]],
        exc_val: typing.Optional[BaseException],
        exc_tb: typing.Optional[types.TracebackType]
    ) -> None:
        """ Do some final checks and complete uploading
        """

        if exc_val is not None:
            self._finalize(exc_val)
            return

        try:
            if self.__uploaded_parts:
                for i in range(max(self.__uploaded_parts) + 1):
                    if i not in self.__uploaded_parts:
                        raise NonSequentialPartNumbers(
                            f'The {i} part is missing!'
                        )
        except BaseException as e:
            self._finalize(e)
            raise

        self._finalize()

    def upload_part(self, data: typing.Union[bytes, bytearray], part_number: int) -> None:
        """ Do some checks and request uploading. The :meth:`.PartsUploaderProto.upload_part` method implementation.
        """
        if part_number in self.__uploaded_parts:
            raise NonSequentialPartNumbers(f'The {part_number} part has been submitted already')

        if self.__final_part is not None and part_number > self.__final_part:
            raise NonSequentialPartNumbers(
                f'The {part_number} part is submitted after the final one ({self.__final_part})'
            )

        part_size = len(data)
        if part_size > self.__part_size:
            raise InvalidPartSize(
                f'Invalid part size -- {part_size}; it must be {self.__part_size} bytes (may be less for a final part)'
            )

        if part_size < self.__part_size:
            if self.__final_part is not None:
                raise InvalidPartSize(
                    f'Invalid part size -- {part_size} for non-final part (which is {self.__final_part})'
                )

            if self.__uploaded_parts and part_number < max(self.__uploaded_parts):
                raise InvalidPartSize(
                    f'Invalid part size -- {part_size} for non-final part'
                )

            self.__final_part = part_number

        self._upload_part(data, part_number)
        self.__uploaded_parts.add(part_number)
