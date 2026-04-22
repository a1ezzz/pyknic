# -*- coding: utf-8 -*-
# pyknic/lib/io/tar/readers.py
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


import contextlib
import dataclasses
import io
import tarfile
import typing

from abc import ABCMeta, abstractmethod

from pyknic.lib.capability import iscapable
from pyknic.lib.io import IOGenerator, IOProducer
from pyknic.lib.io.aio_wrapper import IOThrottler
from pyknic.lib.io.aligner import ChunkReader
from pyknic.lib.io.clients.proto import IOClientProto


class TarReaderEntry:
    """This class helps to read tar entry in a safe way.
    """

    def __init__(self, tar_info: tarfile.TarInfo, chunk_reader: ChunkReader, offset: int, header_size: int) -> None:
        """Create new entry.

        :param tar_info: information about inner entry
        :param chunk_reader: content of inner entry that must be read before the request for the next entry.
        :param offset: offset to the start of this record from the very beginning
        :param header_size: size of the tar-info
        """
        self.__data_read = 0
        self.__tar_info = tar_info
        self.__chunk_reader = chunk_reader
        self.__offset = offset
        self.__header_size = header_size
        self.__wasted = False

    def head_offset(self) -> int:
        """ Return offset where this entry starts. The value may be misleading since the file reading may start not
        from the beginning
        """
        return self.__offset

    def head_size(self) -> int:
        """ The size of of the tar info
        """
        return self.__header_size

    def data_read(self) -> int:
        """ Return number of bytes that has been read already
        """
        return self.__data_read

    def size(self) -> int:
        """ Return number of bytes this entry occupies (tar info + data + padding)
        """
        result = self.head_size()

        result += ((self.__tar_info.size // tarfile.BLOCKSIZE) * tarfile.BLOCKSIZE)
        if (self.__tar_info.size % tarfile.BLOCKSIZE) != 0:
            result += tarfile.BLOCKSIZE

        return result

    def is_wasted(self) -> bool:
        """ Return True if data fully read.
        """
        return self.__wasted

    def tar_info(self) -> tarfile.TarInfo:
        """ Return information about inner entry
        """
        return self.__tar_info

    def read(self) -> bytes:
        """ Read all the entry data and return it at once
        """
        return b''.join(self.data())

    def flush(self) -> None:
        """ Read all the entry data and skip it
        """
        for _ in self.data():
            pass

    def data(self) -> IOGenerator:
        """ Read data related to this entry
        """

        while self.__data_read < self.__tar_info.size:
            bytes_left = self.__tar_info.size - self.__data_read
            max_chunks = (bytes_left // tarfile.BLOCKSIZE) + (0 if bytes_left % tarfile.BLOCKSIZE == 0 else 1)
            next_chunk = self.__chunk_reader.next_chunk(1, max_chunks)

            assert((len(next_chunk) % tarfile.BLOCKSIZE) == 0)

            if len(next_chunk) > bytes_left:
                self.__data_read += bytes_left
                yield next_chunk[:bytes_left]
            else:
                self.__data_read += len(next_chunk)
                yield next_chunk

        self.__wasted = True


class TarArchiveReaderProto(metaclass=ABCMeta):
    """ Prototype for reader that is able to process tar-archive
    """

    @abstractmethod
    def inner_entries(self, *entries_names: str) -> typing.Generator[TarReaderEntry, None, None]:
        """ Read data and yield information about inner files. Entries are returned one by one. Each entry must
        be read with the :meth:`.TarReaderEntry.data` (or :meth:`.TarReaderEntry.read` or :meth:`.TarReaderEntry.flush`)
        method before the request for the next entry.

        :param entries_names: if defined then this method should return only this files/directories/links
        """
        raise NotImplementedError('This method is abstract')

    @abstractmethod
    def entry(self, entry_name: str) -> TarReaderEntry:
        """ Return description and data for a single archive entry

        :param entry_name: name of the archive entry to retreive
        """
        raise NotImplementedError('This method is abstract')


@dataclasses.dataclass
class _FilthyTarEntry:
    """ This class helps to track tar entries while reading. Using it in other modules should be avoided. Better choose
    :class:`.TarReaderEntry`
    """

    source: ChunkReader           # source of the data
    binary_info: bytes            # original tar header (may be larger than tarfile.BLOCKSIZE when it is combined
    # from several extended entries)
    parsed_info: tarfile.TarInfo  # tar header
    offset: int                   # offset of this header from the very beginning

    def data(self) -> IOGenerator:
        """ Read data related to this entry
        """
        counter = self.parsed_info.size

        while counter > 0:
            max_chunks = (counter // tarfile.BLOCKSIZE) + (0 if counter % tarfile.BLOCKSIZE == 0 else 1)
            next_chunk = self.source.next_chunk(1, max_chunks)

            assert((len(next_chunk) % tarfile.BLOCKSIZE) == 0)
            yield next_chunk
            counter -= len(next_chunk)


class _TarReader:
    """ This class helps to read data from a tar archive. Since it scans through all the data it may be unacceptable
    slowly. Use it on you own risk
    """

    zero_block = b'\x00' * tarfile.BLOCKSIZE

    # noinspection PyMethodMayBeStatic
    def _is_regular_entry(self, entry: tarfile.TarInfo) -> bool:
        """ Return True if entry is FS-representable entry like file, directory or some named socket.

        :param entry: entry to check
        """

        regular_entries = [
            tarfile.REGTYPE,
            tarfile.AREGTYPE,
            tarfile.LNKTYPE,
            tarfile.SYMTYPE,
            tarfile.CHRTYPE,
            tarfile.BLKTYPE,
            tarfile.DIRTYPE,
            tarfile.FIFOTYPE,

            # there is tarfile.CONTTYPE also, but what the fuck is this?!
        ]

        return entry.type in regular_entries

    # noinspection PyMethodMayBeStatic
    def _is_extended_head_entry(self, entry: tarfile.TarInfo) -> bool:
        """ Return True if entry is a special one dedicated to overcome original TAR limits (like path limitations
        or size limitations)

        :param entry: entry to check
        """
        extended_head_types = [
            tarfile.GNUTYPE_LONGNAME,  # GNU format
            tarfile.GNUTYPE_LONGLINK,  # GNU format
            tarfile.GNUTYPE_SPARSE,    # GNU format
            tarfile.XHDTYPE            # PAX format

            # tarfile.XGLTYPE -- this is PAX format, but wtf?!
            # tarfile.SOLARIS_XHDTYPE -- some old shit
        ]

        return entry.type in extended_head_types

    # noinspection PyMethodMayBeStatic
    def _next_raw_entries(self, chunk_reader: ChunkReader, start_offset: int) -> _FilthyTarEntry:
        """ Iterate over all entries in source. Extended headers will be split and yielded independently
        """

        next_chunk = chunk_reader.next_chunk(1, 1)
        while next_chunk == self.zero_block:
            start_offset += len(next_chunk)
            next_chunk = chunk_reader.next_chunk(1, 1)

        head = tarfile.TarInfo.frombuf(next_chunk, tarfile.ENCODING, 'strict')  # read the
        # https://docs.python.org/3/library/codecs.html#error-handlers
        return _FilthyTarEntry(chunk_reader, next_chunk, head, start_offset)

    def _next_extended_entry(self, chunk_reader: ChunkReader, start_offset: int) -> _FilthyTarEntry:
        """ Iterate over all entries in source. Extended headers will be combined and only "regular" entries will be
        yielded.
        """

        tar_entry = self._next_raw_entries(chunk_reader, start_offset)
        tar_head = tar_entry.parsed_info

        if self._is_regular_entry(tar_head):
            return tar_entry

        if self._is_extended_head_entry(tar_head):

            extended_head_data = tar_entry.binary_info
            next_entry_offset = start_offset + len(tar_entry.binary_info)
            for chunk in tar_entry.data():
                extended_head_data += chunk
                next_entry_offset += len(chunk)

            next_entry = self._next_raw_entries(chunk_reader, next_entry_offset)
            while not self._is_regular_entry(next_entry.parsed_info):
                if not self._is_extended_head_entry(next_entry.parsed_info):
                    raise ValueError(
                        f'Unknown tar entry spotted -- {str(tar_head.type)} (file -- {str(tar_head.name)})'
                    )

                extended_head_data += next_entry.binary_info
                next_entry_offset += len(next_entry.binary_info)
                for chunk in next_entry.data():
                    extended_head_data += chunk
                    next_entry_offset += len(chunk)

                next_entry = self._next_raw_entries(chunk_reader, next_entry_offset)

            extended_head_data += next_entry.binary_info

            combined_head = tarfile.TarFile(fileobj=io.BytesIO(extended_head_data)).next()
            assert(combined_head is not None)
            return _FilthyTarEntry(next_entry.source, extended_head_data, combined_head, start_offset)

        raise ValueError(f'Unknown tar entry spotted -- {str(tar_head.type)} (file -- {str(tar_head.name)})')

    def iterate_entries(self, data: IOProducer, *entries_names: str) -> typing.Generator[TarReaderEntry, None, None]:
        """ Yield information about inner files
        """

        with contextlib.suppress(StopIteration):
            chunk_reader = ChunkReader(data, tarfile.BLOCKSIZE, strict_mode=True)
            offset = 0
            while True:
                filthy_entry = self._next_extended_entry(chunk_reader, offset)
                reader_entry = TarReaderEntry(
                    filthy_entry.parsed_info, chunk_reader, offset, len(filthy_entry.binary_info)
                )

                if not entries_names or reader_entry.tar_info().name in entries_names:
                    yield reader_entry
                elif entries_names:
                    reader_entry.flush()

                if not reader_entry.is_wasted():
                    raise RuntimeError('You must read data from previous entry before requesting a next one')

                offset += reader_entry.size()


class IOTarArchiveReader(TarArchiveReaderProto):
    """ This reader implementation reads data sequentially so it is more robust but has huge performance penalties
    for the :meth:`TarArchiveReaderProto.inner_descriptors` method implementation

    :note: Please be advised, that the :meth:`TarArchiveReaderProto.entry` implementation is slow since it is required
    to read through the data
    """

    def __init__(self, source: IOProducer):
        """ This implementation reads tar-archive from :class:`.IOProducer`

        :param source: tar-archive data to read
        """
        TarArchiveReaderProto.__init__(self)
        self.__source = source
        self.__source_read = False

    def __non_thread_safe_flag(self) -> None:
        """ This method checks that the source has been read already
        """
        if self.__source_read:
            raise ValueError(f'The source of this reader ({repr(self)}) has been read already.)')
        self.__source_read = True

    def inner_entries(self, *entries_names: str) -> typing.Generator[TarReaderEntry, None, None]:
        """ The :meth:`.TarArchiveReaderProto.entries` method implementation.
        """
        self.__non_thread_safe_flag()
        yield from _TarReader().iterate_entries(self.__source, *entries_names)

    def entry(self, entry_name: str) -> TarReaderEntry:
        """ The :meth:`.TarArchiveReaderProto.entry` method implementation.

        :note: Please be advised, that this method implementation is slow since it is required to read through the data
        """
        self.__non_thread_safe_flag()

        for i in _TarReader().iterate_entries(self.__source):
            if i.tar_info().name == entry_name:
                return i

            for _ in i.data():
                pass

        raise FileNotFoundError(f'The entry "{entry_name}" does not exist')


class ClientTarArchiveReader(TarArchiveReaderProto):
    """ Read a file with the :class:`.IOClientProto` client
    """

    def __init__(self, client: IOClientProto, archive_file: str) -> None:
        """ Create a new reader

        :param client: client to use (to fetch a file)
        :param archive_file: archive file to read
        """
        TarArchiveReaderProto.__init__(self)
        self.__client = client
        self.__archive_file = archive_file

        if not iscapable(self.__client, IOClientProto.receive_file):
            raise ValueError(
                f'The client from the "{repr(self.__client)}" does not implement the "receive_file" capability'
            )

        if not iscapable(self.__client, IOClientProto.receive_file_with_offset):
            raise ValueError(
                f'The client from the "{repr(self.__client)}"'
                ' does not implement the "receive_file_with_offset" capability'
            )

    def inner_entries(self, *entries_names: str) -> typing.Generator[TarReaderEntry, None, None]:
        """ The :meth:`.TarArchiveReaderProto.entries` method implementation."""
        data = self.__client.receive_file(self.__archive_file)
        yield from _TarReader().iterate_entries(data, *entries_names)

    def entry(self, entry_name: str) -> TarReaderEntry:
        """ The :meth:`.TarArchiveReaderProto.entry` method implementation."""

        offset = 0

        with contextlib.suppress(StopIteration):
            while True:
                data = self.__client.receive_file_with_offset(self.__archive_file, offset)

                tar_entry = next(_TarReader().iterate_entries(data))
                tar_info = tar_entry.tar_info()

                if tar_info.name == entry_name:
                    return tar_entry

                offset += tar_entry.head_offset() + tar_entry.size()

        raise FileNotFoundError(f'The entry "{entry_name}" does not exist')


class FileObjectTarReader(TarArchiveReaderProto):
    """ Read a file-object
    """

    def __init__(self, archive_file: typing.IO[bytes]) -> None:
        """ Create a new reader

        :param archive_file: archive file to read
        """
        TarArchiveReaderProto.__init__(self)
        self.__archive_file = archive_file

    def inner_entries(self, *entries_names: str) -> typing.Generator[TarReaderEntry, None, None]:
        """ The :meth:`.TarArchiveReaderProto.inner_entries` method implementation."""

        io_reader = IOTarArchiveReader(IOThrottler.sync_reader(self.__archive_file))
        yield from io_reader.inner_entries(*entries_names)

    def entry(self, entry_name: str) -> TarReaderEntry:
        """ The :meth:`.TarArchiveReaderProto.entry` method implementation."""

        with tarfile.open(fileobj=self.__archive_file, mode='r') as tar:

            try:
                info = tar.getmember(entry_name)
            except KeyError:
                raise FileNotFoundError(f'The entry "{entry_name}" does not exist')

            self.__archive_file.seek(info.offset_data, io.SEEK_SET)

            chunks_count, chunks_extra = divmod(info.size, tarfile.BLOCKSIZE)
            if chunks_extra:
                chunks_count += 1

            return TarReaderEntry(
                info,
                ChunkReader(
                    IOThrottler.sync_reader(self.__archive_file, read_size=(chunks_count * tarfile.BLOCKSIZE)),
                    tarfile.BLOCKSIZE,
                    strict_mode=True
                ),
                info.offset_data,
                len(info.tobuf())
            )
