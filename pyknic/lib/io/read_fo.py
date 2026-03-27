# -*- coding: utf-8 -*-
# pyknic/lib/io/read_fo.py
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

import contextlib
import io

from pyknic.lib.io import IOProducer


class ReadFileObject(io.RawIOBase):
    """ This adapter helps to retrieve data from IOProducer the way file-objects do
    """

    def __init__(self, source: IOProducer) -> None:
        """ Create an adapter

        :param source: data that will be read
        """
        io.RawIOBase.__init__(self)
        self.__source = (x for x in source)  # forces to become generator
        self.__cache = b''
        self.__closed = False

    def close(self) -> None:
        """ Close the file-object (the :meth:`io.IOBase.close` method implementation)
        """
        if not self.__closed:
            self.__source.close()
        self.__closed = True

    @property
    def closed(self) -> bool:
        """ Check if the file-object is closed (the :meth:`io.IOBase.closed` method implementation)
        """
        return self.__closed

    def readable(self) -> bool:
        """ Check if the file-object is "readable" (supports some read methods)
        (the :meth:`io.IOBase.closed` method implementation)
        """
        return True

    def seekable(self) -> bool:
        """ Check if the file-object is "seekable" (supports seek, tell and truncate methods)
        (the :meth:`io.IOBase.closed` method implementation)
        """
        return False

    def writable(self) -> bool:
        """ Check if the file-object is "writable" (supports write and truncate methods)
        (the :meth:`io.IOBase.closed` method implementation)
        """
        return False

    def isatty(self) -> bool:
        """ Check if the file-object is interactive, like tty (the :meth:`io.IOBase.closed` method implementation)
        """
        return False

    def fileno(self) -> int:
        """ Original method returns the underlying file descriptor or raises the OSError if unsupported. This
        implementation raises exception all the time (the :meth:`io.IOBase.fileno` method implementation)
        """
        raise OSError('The "fileno" method is not suitable for the ReadFileObject class')

    def read(self, size: int = -1, /) -> bytes:
        """ Read data from original source (the :meth:`io.RawIOBase.read` method implementation)

        :param size: size of data to read
        """

        if self.__closed:
            raise ValueError('ReadFileObject is closed')

        def chop_cache() -> bytes:
            result = self.__cache[:size] if size >= 0 else self.__cache
            self.__cache = self.__cache[len(result):]
            return result

        if len(self.__cache) >= size >= 0:
            return chop_cache()

        with contextlib.suppress(StopIteration):
            while size < 0 or len(self.__cache) < size:
                self.__cache += next(self.__source)

        return chop_cache()
