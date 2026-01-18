# -*- coding: utf-8 -*-
# pyknic/lib/io/tar.py
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

import datetime
import grp
import os
import pathlib
import pwd
import tarfile
import typing

from pyknic.lib.verify import verify_value
from pyknic.lib.io import IOGenerator
from pyknic.lib.io.aligner import Aligner
from pyknic.lib.io.aio_wrapper import IOThrottler


class _TarPaddingGenerator:
    """This class calculates required padding and write it
    """

    @verify_value(aligned_to=lambda x: x > 0)
    def __init__(self, aligned_to: int):
        """Create new padding helper

        :param aligned_to: number of bytes required for padding
        """
        self.__aligned_to = aligned_to if aligned_to else tarfile.BLOCKSIZE
        self.__counter = 0

    def write(self, data: IOGenerator) -> IOGenerator:
        """This processor writes data and required padding

        :param data: data to write
        """
        aligner = Aligner(self.__aligned_to)

        for block in aligner.iterate_data(data):
            self.__counter += len(block)
            yield block

        _, extra_bytes = divmod(self.__counter, self.__aligned_to)
        delta = (self.__aligned_to - extra_bytes) if extra_bytes else self.__aligned_to
        yield (tarfile.NUL * delta) if delta else b''


class TarInnerFileGenerator(_TarPaddingGenerator):
    """This class helps to save a single file inside a tar archive.
    """

    def __init__(self):
        """Create a new file writer
        """
        _TarPaddingGenerator.__init__(self, tarfile.BLOCKSIZE)

    def _custom_tar_info(
        self,
        filename: str,
        /,
        size: typing.Optional[int] = None,
        mtime: typing.Optional[int] = None,
        mode: typing.Optional[int] = None,
        uid: typing.Optional[int] = None,
        gid: typing.Optional[int] = None,
        uname: typing.Optional[str] = None,
        gname: typing.Optional[str] = None,
    ) -> tarfile.TarInfo:
        """Generate meta-info for a single file inside archive

        :param filename: filename of an inner file
        :param size: size of file (zero by default)
        :param mtime: file modification time (is now by default)
        :param mode: file mode (0440 by default)
        :param uid: file UID (current process user is used by default)
        :param gid: file GID (current process group is used by default)
        :param uname: username related to uid
        :param gname: group name related to gid
        """
        tar_info = tarfile.TarInfo(name=filename)
        if size is not None:
            tar_info.size = size
        tar_info.mtime = mtime if mtime is not None else int(datetime.datetime.now().timestamp())
        tar_info.mode = mode if mode is not None else int('440', base=8)
        tar_info.type = tarfile.REGTYPE
        tar_info.uid = uid if uid is not None else os.getuid()
        tar_info.gid = gid if gid is not None else os.getgid()
        tar_info.uname = uname if uname is not None else pwd.getpwuid(tar_info.uid).pw_name
        tar_info.gname = gname if gname is not None else grp.getgrgid(tar_info.gid).gr_name

        return tar_info

    def _tar_info_by_file(self, filename: typing.Union[str, pathlib.Path]) -> tarfile.TarInfo:
        """Retrieve meta-info by a real file

        :param filename: file name which meta-info should be retrieved
        """
        # TODO: filename related to some directory?!
        tar_file = tarfile.TarFile('/dev/zero', mode='w')  # TODO: it seams bogus
        return tar_file.gettarinfo(filename)

    def file(self, source: typing.Union[str, pathlib.Path]) -> IOGenerator:
        """Generate data required to save a file inside a tar archive

        :param source: a path to a file to archive
        """

        def data_generator() -> IOGenerator:
            tar_info = self._tar_info_by_file(source)
            yield tar_info.tobuf()

            with open(source, 'rb') as f:
                # TODO: consider checking that file modification time hasn't changed!

                for chunk in IOThrottler.sync_reader(f):
                    yield chunk

        yield from self.write(data_generator())

    def generator(
        self,
        source: IOGenerator,
        data_size: int,
        filename: str,
        /,
        mtime: typing.Optional[int] = None,
        mode: typing.Optional[int] = None,
        uid: typing.Optional[int] = None,
        gid: typing.Optional[int] = None,
        uname: typing.Optional[str] = None,
        gname: typing.Optional[str] = None,
    ) -> IOGenerator:
        """Generate data required to save custom data inside a tar archive

        :param source: a data to save
        :param filename: name of an inner file
        :param data_size: number of bytes that source has. It must be exact number of bytes (not more, not less)

        :param mtime: file modification time (is now by default)
        :param mode: file mode (0440 by default)
        :param uid: file UID (current process user is used by default)
        :param gid: file GID (current process group is used by default)
        :param uname: username related to uid
        :param gname: group name related to gid
        """

        if filename.startswith('/'):
            raise ValueError('File path must be relative')

        def data_generator() -> IOGenerator:
            tar_info = self._custom_tar_info(
                filename,
                size=data_size,
                mtime=mtime,
                mode=mode,
                uid=uid,
                gid=gid,
                uname=uname,
                gname=gname,
            )
            yield tar_info.tobuf()

            calculated_size = 0
            for data in source:
                calculated_size += len(data)
                if calculated_size > data_size:
                    raise ValueError(
                        'Original data has more bytes than expected. '
                        f'Expected -- {data_size}, found -- {calculated_size}'
                    )

                yield data

            if calculated_size != data_size:
                raise ValueError(
                    'Incorrect number of bytes in original data. '
                    f'Expected -- {data_size}, found -- {calculated_size}'
                )

        yield from self.write(data_generator())


class TarArchiveGenerator(_TarPaddingGenerator):
    """This class helps to save a single tar archive.
    """

    def __init__(self):
        """Create a new tar archive writer
        """
        _TarPaddingGenerator.__init__(self, aligned_to=tarfile.RECORDSIZE)
