# -*- coding: utf-8 -*-
# pyknic/lib/tar_archiver.py
#
# Copyright (C) 2025 the pyknic authors and contributors
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
import types
import typing

from pyknic.lib.verify import verify_value
from pyknic.lib.io import IOGenerator
from pyknic.lib.io.aio_wrapper import IOThrottler, cag


class _TarArchiverContext:
    """This context relates to a new archive creation
    """

    @verify_value(block_size=lambda x: x is None or x > 0)
    def __init__(
        self, destination: io.BufferedRandom, block_size: typing.Optional[int] = None, truncate_on_error: bool = True
    ):
        """Create a new context

        :param destination: Tar archive that will be created (it resets content also)
        :param block_size: number of byte to read one at a time
        """
        self.__archive = destination
        self.__block_size = block_size if block_size is not None else 4096
        self.__truncate_on_error = truncate_on_error

        self.__total_bytes = 0
        self.__context_inited = False

    async def open(self) -> None:
        """Initialize context. This method is called automatically with the "async with" call
        """
        self.__context_inited = True

    async def __aenter__(self) -> '_TarArchiverContext':
        """Enter this context
        """
        await self.open()
        return self

    def __custom_tar_info(
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

    def __tar_info_by_file(self, filename: typing.Union[str, pathlib.Path]) -> tarfile.TarInfo:
        """Retrieve meta-info by a real file

        :param filename: file name which meta-info should be retrieved
        """
        # TODO: filename related to some directory?!
        tar_file = tarfile.TarFile('/dev/zero', mode='w')  # TODO: it seams bogus
        return tar_file.gettarinfo(filename)

    def __padding(self, written_bytes: int, bytes_align_to: int) -> bytes:
        """Return bytes that are needed for tar padding

        :param written_bytes: number of bytes has been written
        :param bytes_align_to: number of bytes to align to
        """
        _, extra_bytes = divmod(written_bytes, bytes_align_to)
        delta = (bytes_align_to - extra_bytes) if extra_bytes else bytes_align_to
        return (tarfile.NUL * delta) if delta else b''

    async def __append_header(self, tar_info: tarfile.TarInfo) -> int:
        """Append an archiving file header to an archive and return its size

        :param tar_info: archive info
        """
        tar_header = tar_info.tobuf()

        header_size = await cag(IOThrottler.async_writer(
            (x for x in (tar_header,)), self.__archive, block_size=self.__block_size
        ))

        self.__total_bytes += header_size
        return header_size

    async def __append_data(
        self, source: typing.Union[io.BytesIO, io.BufferedReader], respect_size: typing.Optional[bool] = None
    ) -> int:
        """Append file data to an archive and return written size

        :param source: source data
        :param respect_size: if defined -- expected file size
        """
        source.seek(0)

        file_bytes = await cag(IOThrottler.async_copier(
            source, self.__archive, block_size=self.__block_size, copy_size=respect_size
        ))

        self.__total_bytes += file_bytes

        # TODO: recover!
        # if respect_size is not None:
        #     if data or file_bytes != respect_size:
        #         raise RuntimeError('It seams that file has been changed during archiving!')
        #
        return file_bytes

    async def __append_file_padding(self, header_size: int, file_bytes: int) -> None:
        """Append single file padding to an archive

        :param header_size: size of tar header related to a file
        :param file_bytes: size of written file
        """
        padding = self.__padding(header_size + file_bytes, tarfile.BLOCKSIZE)

        self.__total_bytes += await cag(IOThrottler.async_writer(
            (x for x in (padding,)), self.__archive, block_size=self.__block_size
        ))

    async def __patch_file_size(
        self, file_start_pos: int, tar_info: tarfile.TarInfo, header_size: int, file_size: int
    ) -> None:
        """Update original file header with new file size

        :param file_start_pos: start inner position of archiving file
        :param tar_info: archive info (aka tar header)
        :param header_size: size of a tar header
        :param file_size: new size of file
        """
        end_pos = self.__archive.tell()
        tar_info.size = file_size
        tar_header = tar_info.tobuf()
        assert(len(tar_header) == header_size)  # check that we didn't change a header size

        self.__archive.seek(file_start_pos, os.SEEK_SET)

        await cag(IOThrottler.async_writer((x for x in (tar_header,)), self.__archive, block_size=self.__block_size))

        self.__archive.seek(end_pos, os.SEEK_SET)

    async def append_file(self, source: typing.Union[str, pathlib.Path]) -> None:
        """Append a file to an archive

        :param source: a path to a file to archive
        """
        if not self.__context_inited:
            raise RuntimeError('Context is not initialized')

        header_size = await self.__append_header(self.__tar_info_by_file(source))

        with open(source, 'rb') as f:
            # TODO: consider checking that file modification time hasn't changed!
            file_bytes = await self.__append_data(f)

        await self.__append_file_padding(header_size, file_bytes)

    async def append_io(
        self,
        source: typing.Union[io.BytesIO, io.BufferedReader],
        filename: str,
        **tar_kwargs: typing.Optional[typing.Union[str, int]]
    ) -> None:
        """Append a custom data to an archive

        :param source: a data to archive
        :param filename: name of a filename to archive
        :param tar_kwargs: extra args to pass to the `:meth:.__custom_tar_info` method
        which is used for tar header creation
        """
        if not self.__context_inited:
            raise RuntimeError('Context is not initialized')

        start_pos = self.__archive.tell()

        tar_info = self.__custom_tar_info(filename, **tar_kwargs)  # type: ignore[arg-type]
        header_size = await self.__append_header(tar_info)
        file_bytes = await self.__append_data(source)
        await self.__append_file_padding(header_size, file_bytes)
        await self.__patch_file_size(start_pos, tar_info, header_size, file_bytes)

    async def append_generator(
        self,
        source: IOGenerator,
        filename: str,
        **tar_kwargs: typing.Optional[typing.Union[str, int]]
    ) -> None:
        """Append data from generator to an archive

        :param source: a data to archive
        :param filename: name of an inner file
        """
        if not self.__context_inited:
            raise RuntimeError('Context is not initialized')

        start_pos = self.__archive.tell()

        tar_info = self.__custom_tar_info(filename, **tar_kwargs)  # type: ignore[arg-type]
        header_size = await self.__append_header(tar_info)

        file_bytes = await cag(IOThrottler.async_writer(
            source, self.__archive, block_size=self.__block_size
        ))
        self.__total_bytes += file_bytes

        await self.__append_file_padding(header_size, file_bytes)
        await self.__patch_file_size(start_pos, tar_info, header_size, file_bytes)

    def __fin_padding(self) -> bytes:
        return self.__padding(self.__total_bytes, tarfile.RECORDSIZE)

    async def close(self) -> None:
        """Close this context and finalize file. Is used in conjunction with the :meth:`._TarArchiveContext.open` method
        Is called automatically when the context is closed.
        """
        await cag(IOThrottler.async_writer((x for x in (self.__fin_padding(),)), self.__archive))

    async def __aexit__(
        self,
        exc_type: typing.Optional[typing.Type[BaseException]],
        exc_val: typing.Optional[BaseException],
        exc_tb: typing.Optional[types.TracebackType]
    ) -> None:
        """Close this context and finalize file.
        """
        if exc_type is None:
            await self.close()

        elif self.__truncate_on_error:
            self.__archive.seek(0, os.SEEK_SET)
            self.__archive.truncate()


class TarArchiver:
    """Wrapper for basic tar functions
    """

    def create(self, destination: io.BufferedRandom, truncate_on_error: bool = True) -> _TarArchiverContext:
        """Return a new tar archiver context. It should be used with the "async with" call
        """
        return _TarArchiverContext(destination, truncate_on_error=truncate_on_error)

    async def open_context(self, destination: io.BufferedRandom, truncate_on_error: bool = True) -> _TarArchiverContext:
        """Return a new tar archiver context that require manual closing procedure. It works without "async with" call
        """
        tar_context = _TarArchiverContext(destination, truncate_on_error=truncate_on_error)
        await tar_context.open()
        return tar_context

    async def extract_io(self, source: io.BufferedRandom, filename: str, destination: io.BufferedRandom) -> None:
        """Extract data from an archive

        :param source: tar-data
        :param filename: name of a file to retrieve from archive
        :param destination: destination io, that should hold data
        """

        start_pos = source.tell()

        with tarfile.open(fileobj=source) as tar:
            tar_info = tar.getmember(filename)
            file_size = tar_info.size
            source.seek(start_pos + tar_info.offset_data, os.SEEK_SET)

            await cag(IOThrottler.async_copier(source, destination, copy_size=file_size))
            source.seek(start_pos, os.SEEK_SET)
