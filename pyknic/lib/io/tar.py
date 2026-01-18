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
import io
import os
import pathlib
import pwd
import tarfile
import typing

from abc import ABCMeta, abstractmethod

from pyknic.lib.verify import verify_value
from pyknic.lib.io import IOGenerator
from pyknic.lib.io.aio_wrapper import IOThrottler, cag


class StaticTarEntryProto(metaclass=ABCMeta):

    @abstractmethod
    def entry(self) -> IOGenerator:
        raise NotImplementedError('This method is abstract')


class DynamicTarEntryProto(metaclass=ABCMeta):

    @abstractmethod
    def entry(self, file_obj: io.BufferedRandom) -> IOGenerator:
        raise NotImplementedError('This method is abstract')


class _TarPaddingGenerator:
    """This class calculates required padding and write it
    """

    @verify_value(aligned_to=lambda x: x > 0)
    @verify_value(min_padding=lambda x: x is None or x > 0)
    def __init__(self, aligned_to: int, min_padding: typing.Optional[int] = None):
        """Create new padding helper

        :param aligned_to: number of bytes required for padding
        """
        self.__aligned_to = aligned_to if aligned_to else tarfile.BLOCKSIZE
        self.__min_padding = min_padding
        self.__counter = 0

    def _write(self, data: IOGenerator) -> IOGenerator:
        """This processor writes data and required padding

        :param data: data to write
        """
        for block in data:
            self.__counter += len(block)
            yield block

        _, extra_bytes = divmod(self.__counter, self.__aligned_to)
        delta = (self.__aligned_to - extra_bytes) if extra_bytes else self.__aligned_to
        if self.__min_padding is not None and delta < self.__min_padding:
            delta += self.__aligned_to
        yield (tarfile.NUL * delta) if delta else b''


class _BaseTarInnerFileGenerator(_TarPaddingGenerator):
    """This class helps to save a custom entry inside a tar archive.
    """

    def __init__(self) -> None:
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


class TarInnerFileGenerator(_BaseTarInnerFileGenerator, StaticTarEntryProto):
    """This class helps to save a static file inside a tar archive.
    """

    def __init__(self, source: typing.Union[str, pathlib.Path]):
        """Create a new inner file generator

        :param source: a path to a file to archive
        """
        _BaseTarInnerFileGenerator.__init__(self)
        self.__source = source

    def entry(self) -> IOGenerator:
        """ :meth:`.StaticTarEntryProto.entry` implementation
        """

        def data_generator() -> IOGenerator:
            tar_info = self._tar_info_by_file(self.__source)
            yield tar_info.tobuf()

            with open(self.__source, 'rb') as f:
                # TODO: consider checking that file modification time hasn't changed!

                for chunk in IOThrottler.sync_reader(f):
                    yield chunk

        yield from self._write(data_generator())


class TarInnerGenerator(_BaseTarInnerFileGenerator, StaticTarEntryProto):
    """This class helps to save a static data (with known size) from generator inside a tar archive.
    """

    def __init__(
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
    ):
        """Create a new inner file generator

        :param source: a data to save
        :param filename: name of an inner file
        :param data_size: number of bytes that source has. It must be exact number of bytes (not more, not less)

        :param mtime: file modification time (is now by default)
        :param mode: file mode (0440 by default)
        :param uid: file UID (current process user is used by default)
        :param gid: file GID (current process group is used by default)
        :param uname: username related to uid
        :param gname: group name related to gid        """
        _BaseTarInnerFileGenerator.__init__(self)

        if filename.startswith('/'):
            raise ValueError('File path must be relative')

        self.__source = source
        self.__data_size = data_size
        self.__filename = filename
        self.__mtime = mtime
        self.__mode = mode
        self.__uid = uid
        self.__gid = gid
        self.__uname = uname
        self.__gname = gname

    def entry(self) -> IOGenerator:
        """ :meth:`.StaticTarEntryProto.entry` implementation
        """

        def data_generator() -> IOGenerator:
            tar_info = self._custom_tar_info(
                self.__filename,
                size=self.__data_size,
                mtime=self.__mtime,
                mode=self.__mode,
                uid=self.__uid,
                gid=self.__gid,
                uname=self.__uname,
                gname=self.__gname,
            )
            yield tar_info.tobuf()

            calculated_size = 0
            for data in self.__source:
                calculated_size += len(data)
                if calculated_size > self.__data_size:
                    raise ValueError(
                        'Original data has more bytes than expected. '
                        f'Expected -- {self.__data_size}, found -- {calculated_size}'
                    )

                yield data

            if calculated_size != self.__data_size:
                raise ValueError(
                    'Incorrect number of bytes in original data. '
                    f'Expected -- {self.__data_size}, found -- {calculated_size}'
                )

        yield from self._write(data_generator())


class TarInnerDynamicGenerator(_BaseTarInnerFileGenerator, DynamicTarEntryProto):
    """This class helps to save a dynamic data from generator (which size is unknown) inside a tar archive.
    """

    def __init__(
        self,
        source: IOGenerator,
        filename: str,
        /,
        mtime: typing.Optional[int] = None,
        mode: typing.Optional[int] = None,
        uid: typing.Optional[int] = None,
        gid: typing.Optional[int] = None,
        uname: typing.Optional[str] = None,
        gname: typing.Optional[str] = None,
    ):
        """Create a new inner file generator

        :param source: a data to save
        :param filename: name of an inner file

        :param mtime: file modification time (is now by default)
        :param mode: file mode (0440 by default)
        :param uid: file UID (current process user is used by default)
        :param gid: file GID (current process group is used by default)
        :param uname: username related to uid
        :param gname: group name related to gid        """
        _BaseTarInnerFileGenerator.__init__(self)

        if filename.startswith('/'):
            raise ValueError('File path must be relative')

        self.__source = source
        self.__filename = filename
        self.__mtime = mtime
        self.__mode = mode
        self.__uid = uid
        self.__gid = gid
        self.__uname = uname
        self.__gname = gname

    def entry(self, file_obj: io.BufferedRandom) -> IOGenerator:
        """ :meth:`.DynamicTarEntryProto.entry` implementation
        """

        def data_generator() -> IOGenerator:
            start_pos = file_obj.tell()

            tar_info = self._custom_tar_info(
                self.__filename,
                size=0,
                mtime=self.__mtime,
                mode=self.__mode,
                uid=self.__uid,
                gid=self.__gid,
                uname=self.__uname,
                gname=self.__gname,
            )
            binary_tar_info = tar_info.tobuf()
            yield binary_tar_info

            data_size = 0
            for chunk in self.__source:
                data_size += len(chunk)
                yield chunk

            end_pos = file_obj.tell()

            tar_info.size = data_size
            patched_tar_info = tar_info.tobuf()
            assert(len(patched_tar_info) == len(binary_tar_info))  # check that we didn't change a header size

            file_obj.seek(start_pos, os.SEEK_SET)
            file_obj.write(patched_tar_info)
            file_obj.seek(end_pos, os.SEEK_SET)

        yield from self._write(data_generator())


class TarArchive(_TarPaddingGenerator):
    """This class helps to save a single tar archive.
    """

    def __init__(self) -> None:
        """Create a new tar archive writer
        """
        _TarPaddingGenerator.__init__(self, aligned_to=tarfile.RECORDSIZE, min_padding=(2 * tarfile.BLOCKSIZE))

    def static_archive(self, sources: typing.Iterable[StaticTarEntryProto]) -> IOGenerator:

        def entries() -> IOGenerator:
            for s in sources:
                yield from s.entry()

        yield from self._write(entries())

    async def dynamic_archive(
        self,
        destination: io.BufferedRandom,
        sources: typing.Iterable[typing.Union[StaticTarEntryProto, DynamicTarEntryProto]],
        write_throttling: typing.Optional[int] = None
    ) -> None:
        destination.seek(0)
        destination.truncate()

        def entries() -> IOGenerator:
            for s in sources:
                if isinstance(s, StaticTarEntryProto):
                    yield from s.entry()
                else:
                    assert(isinstance(s, DynamicTarEntryProto))
                    yield from s.entry(destination)

        await cag(IOThrottler.async_writer(self._write(entries()), destination, throttling=write_throttling))

    def extract(self, source: io.BufferedRandom, filename: str) -> IOGenerator:
        """Extract data from an archive

        :param source: tar-data
        :param filename: name of a file to retrieve from archive
        """

        start_pos = source.tell()

        with tarfile.open(fileobj=source) as tar:
            tar_info = tar.getmember(filename)
            file_size = tar_info.size
            source.seek(start_pos + tar_info.offset_data, os.SEEK_SET)

            yield from IOThrottler.sync_reader(source, read_size=file_size)

            source.seek(start_pos, os.SEEK_SET)
