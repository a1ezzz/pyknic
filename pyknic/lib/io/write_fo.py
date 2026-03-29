# -*- coding: utf-8 -*-
# pyknic/lib/io/write_fo.py
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

import io
import os
import typing

from pyknic.lib.io import IOGenerator
from pyknic.lib.io.aio_wrapper import IOThrottler
from pyknic.lib.tasks.threaded_task import ThreadRunner


class WriteFileObject(io.RawIOBase):
    """ This adapter help to retrieve data that was written in a file-a-like object.
    """

    def __init__(self, command: typing.Callable[[typing.BinaryIO], typing.Any]) -> None:
        """ Create an adapter

        :param command: command to execute (it must accept the only argument -- a file object this function will be
        writing to)
        """

        # TODO: try to make it with the optional :class:`ThreadExecutor`
        self.__command = command

    def __call__(self) -> IOGenerator:
        """ Execute the command and receive written data
        """

        read_fd_int, write_fd_int = os.pipe()

        def writer_fn() -> None:
            with os.fdopen(write_fd_int, 'wb') as f:
                self.__command(f)

        with ThreadRunner.task(writer_fn):
            read_fd_obj = os.fdopen(read_fd_int, 'rb')
            yield from IOThrottler.sync_reader(read_fd_obj)
