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

import contextlib
import dataclasses
import datetime
import grp
import io
import os
import pathlib
import pwd
import tarfile
import typing

from abc import ABCMeta, abstractmethod

from pyknic.lib.capability import iscapable
from pyknic.lib.io import IOGenerator, IOProducer
from pyknic.lib.io.aio_wrapper import IOThrottler, cag
from pyknic.lib.io.aligner import ChunkReader
from pyknic.lib.io.clients.collection import IOVirtualClient
from pyknic.lib.io.clients.proto import IOClientProto
from pyknic.lib.uri import URI
from pyknic.lib.verify import verify_value


MAX_DYNAMIC_FILE_SIZE = (2 ** 10) ** 7  # This is a maximum number of bytes (1 zebibyte) that may be saved "dynamically"
# Dynamically means that a size of data is unknown at archiving startup.
# Units:
#   kibi  Ki 2^10
#   mebi  Mi 2^20
#   gibi  Gi 2^30
#   tebi  Ti 2^40
#   pebi  Pi 2^50
#   exbi  Ei 2^60
#   zebi  Zi 2^70
#   yobi  Yi 2^80
#   robi  Ri 2^90
#   quebi Qi 2^100
#
# Note. The maximum volume size for EXT4 is 1 exbibyte


class StaticTarEntryProto(metaclass=ABCMeta):
    """This class describes tar entry which size is known before start
    """

    @abstractmethod
    def entry(self) -> IOGenerator:
        """Yield bytes that describe tar header and data.
        """
        raise NotImplementedError('This method is abstract')


class DynamicTarEntryProto(metaclass=ABCMeta):
    """This class describes tar entry which size is unknown

    :note: please note the MAX_DYNAMIC_FILE_SIZE
    """

    @abstractmethod
    def entry(self, file_obj: typing.IO[bytes]) -> IOGenerator:
        """Yield bytes that describe tar header and data.

        :param file_obj: file object to which data is written. Header and content must be yielded, but this object
        may be used for patching header only
        """
        raise NotImplementedError('This method is abstract')

    @abstractmethod
    def tar_info(self, size: int, expected_header_size: typing.Optional[int] = None) -> bytes:
        """ Return binary representation of this entry

        :param size: an entry size. Sometimes it is safe to use MAX_DYNAMIC_FILE_SIZE and later regenerate this header
        with much lower value
        :param expected_header_size: size of header that should be generated. If possible then the final header will be
        padded with some unimportant metainformation in order to match this size.
        """
        raise NotImplementedError('This method is abstract')

    @abstractmethod
    def data(self) -> IOGenerator:
        """ Return data of this entry
        """
        raise NotImplementedError('This method is abstract')


class _TarPaddingGenerator:
    """This class calculates required padding and write it
    """

    @verify_value(aligned_to=lambda x: x > 0)
    def __init__(self, aligned_to: int, extra_padding: bool = False):
        """Create new padding helper

        :param aligned_to: number of bytes required for padding
        :param extra_padding: whether extra padding block should be appended at the end
        """
        self.__aligned_to = aligned_to if aligned_to else tarfile.BLOCKSIZE
        self.__extra_padding = extra_padding
        self.__counter = 0

    def _write(self, data: IOProducer) -> IOGenerator:
        """This processor writes data and required padding

        :param data: data to write
        """
        for block in data:
            self.__counter += len(block)
            yield block

        extra_bytes = self.__counter % self.__aligned_to
        delta = (self.__aligned_to - extra_bytes) if extra_bytes else 0
        if self.__extra_padding:
            delta += self.__aligned_to
        yield (b'\0' * delta) if delta else b''


class _BaseTarInnerFileGenerator(_TarPaddingGenerator):
    """This class helps to save a custom entry inside a tar archive.
    """

    def __init__(self) -> None:
        """Create a new file writer
        """
        _TarPaddingGenerator.__init__(self, tarfile.BLOCKSIZE)

    # noinspection PyMethodMayBeStatic
    def __pax_headers_padding(self, tar_info: tarfile.TarInfo, expected_size: int) -> tarfile.TarInfo:
        """Fill comment section in PAX header in order to comply limitations

        :param tar_info: original header to update
        :param expected_size: expected size of tar header
        """

        if expected_size % tarfile.BLOCKSIZE != 0:
            raise ValueError('Expected tar header is not aligned with the blocksize')

        if len(tar_info.tobuf()) > expected_size:
            raise ValueError('Original tar header is more than expected size')

        comment_chunk = 'pyknic-' + ('-c' * 60) + ';'  # 128 bytes
        tar_info.pax_headers['comment'] = comment_chunk  # type: ignore[index]
        while len(tar_info.tobuf()) < expected_size:
            tar_info.pax_headers['comment'] += comment_chunk  # type: ignore[index]

        if len(tar_info.tobuf()) != expected_size:
            raise ValueError('Unable to align tar header')

        return tar_info

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
        expected_header_size: typing.Optional[int] = None,
    ) -> tarfile.TarInfo:
        """Generate meta-info for a single file inside archive.

        :param filename: filename of an inner file.
        :param size: size of file (zero by default).
        :param mtime: file modification time (is now by default).
        :param mode: file mode (0440 by default).
        :param uid: file UID (current process user is used by default).
        :param gid: file GID (current process group is used by default).
        :param uname: username related to uid.
        :param gname: group name related to gid.
        :param expected_header_size: if specified then it is number of bytes that tar header should have.
        (result may have extra comment message in PAX header in order to achieve expectations)
        """
        if filename.startswith('/'):
            raise ValueError('Tar entries should not have absolute path because of possible tar bomb')

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

        if expected_header_size is not None and len(tar_info.tobuf()) != expected_header_size:
            tar_info = self.__pax_headers_padding(tar_info, expected_header_size)

        return tar_info

    # noinspection PyMethodMayBeStatic
    def _tar_info_by_file(self, filename: typing.Union[str, pathlib.Path]) -> tarfile.TarInfo:
        """Retrieve meta-info by a real file

        :param filename: file name which meta-info should be retrieved
        """
        # TODO: filename related to some directory?!
        tar_file = tarfile.TarFile('/dev/zero', mode='w')  # TODO: it seams bogus
        tar_info = tar_file.gettarinfo(filename)

        if tar_info.name.startswith('/'):
            raise ValueError('Tar entries should not have absolute path because of possible tar bomb')

        return tar_info


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

            source = pathlib.Path(self.__source)
            if source.is_file():

                with open(source, 'rb') as f:
                    # TODO: consider checking that file modification time hasn't changed!

                    for chunk in IOThrottler.sync_reader(f):
                        yield chunk

        yield from self._write(data_generator())


class TarInnerGenerator(_BaseTarInnerFileGenerator, StaticTarEntryProto):
    """This class helps to save a static data (with known size) from generator inside a tar archive.
    """

    def __init__(
        self,
        source: IOProducer,
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
        source: IOProducer,
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

    def tar_info(self, size: int, expected_header_size: typing.Optional[int] = None) -> bytes:

        if expected_header_size is None:
            info = self._custom_tar_info(
                self.__filename,
                size=size,
                mtime=self.__mtime,
                mode=self.__mode,
                uid=self.__uid,
                gid=self.__gid,
                uname=self.__uname,
                gname=self.__gname,
            )
        else:
            info = self._custom_tar_info(
                self.__filename,
                size=size,
                mtime=self.__mtime,
                mode=self.__mode,
                uid=self.__uid,
                gid=self.__gid,
                uname=self.__uname,
                gname=self.__gname,
                expected_header_size=expected_header_size
            )

        return info.tobuf()

    def data(self) -> IOGenerator:
        yield from self.__source

    @verify_value(file_obj=lambda x: x.seekable())
    def entry(self, file_obj: typing.IO[bytes]) -> IOGenerator:
        """ :meth:`.DynamicTarEntryProto.entry` implementation
        """

        def data_generator() -> IOGenerator:
            start_pos = file_obj.tell()

            binary_tar_info = self.tar_info(MAX_DYNAMIC_FILE_SIZE)
            yield binary_tar_info

            data_size = 0
            for chunk in self.__source:
                data_size += len(chunk)

                if data_size > MAX_DYNAMIC_FILE_SIZE:
                    raise ValueError('Are you saving the universe?!')

                yield chunk

            end_pos = file_obj.tell()

            patched_tar_info = self.tar_info(data_size, len(binary_tar_info))
            assert(len(binary_tar_info) == len(patched_tar_info))

            file_obj.seek(start_pos, os.SEEK_SET)
            file_obj.write(patched_tar_info)
            file_obj.seek(end_pos, os.SEEK_SET)

        yield from self._write(data_generator())


@dataclasses.dataclass
class _FilthyTarEntry:
    """This class helps to track tar entries while reading. Using it in other modules should be avoided. Better choose
    :class:`.DecentTarEntry`
    """

    source: ChunkReader           # source of the data
    binary_info: bytes            # original tar header (may be larger than tarfile.BLOCKSIZE when it is combined
    # from several extended entries)
    parsed_info: tarfile.TarInfo  # tar header
    offset: int                   # offset of this header from the very beggining

    def data(self) -> IOGenerator:
        """Read data related to this entry
        """
        counter = self.parsed_info.size

        while counter > 0:
            max_chunks = (counter // tarfile.BLOCKSIZE) + (0 if counter % tarfile.BLOCKSIZE == 0 else 1)
            next_chunk = self.source.next_chunk(1, max_chunks)

            assert((len(next_chunk) % tarfile.BLOCKSIZE) == 0)
            yield next_chunk
            counter -= len(next_chunk)


class DecentTarEntry:
    """This class helps to read tar entry in a safe way.
    """

    def __init__(self, tar_info: tarfile.TarInfo, chunk_reader: ChunkReader, offset: int, header_size: int) -> None:
        """Create new entry.

        :param tar_info: information about inner entry
        :param chunk_reader: content of inner entry that must be read before the request for the next entry.
        :param offset: offset to the start of this record from the very beggining
        """
        self.__data_read = 0
        self.__tar_info = tar_info
        self.__chunk_reader = chunk_reader
        self.__offset = offset
        self.__header_size = header_size
        self.__wasted = False

    def head_offset(self) -> int:
        return self.__offset

    def head_size(self) -> int:
        return self.__header_size

    def data_read(self) -> int:
        return self.__data_read

    def is_wasted(self) -> bool:
        """Return True if data fully read.
        """
        return self.__wasted

    def tar_info(self) -> tarfile.TarInfo:
        """Return information about inner entry
        """
        return self.__tar_info

    def data(self) -> IOGenerator:
        """Read data related to this entry
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


class _TarReader:
    """This class helps to read data from a tar archive. Since it scans through all the data it may be unacceptable
    slowly. Use it on you own risk
    """

    zero_block = b'\x00' * tarfile.BLOCKSIZE

    # noinspection PyMethodMayBeStatic
    def _is_regular_entry(self, entry: tarfile.TarInfo) -> bool:
        """Return True if entry is FS-representable entry like file, directory or some named socket.

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
        """Return True if entry is a special one dedicated to overcome original TAR limits (like path limitations
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
        """Iterate over all entries in source. Extended headers will be split and yielded independently
        """

        next_chunk = chunk_reader.next_chunk(1, 1)
        while next_chunk == self.zero_block:
            start_offset += len(next_chunk)
            next_chunk = chunk_reader.next_chunk(1, 1)

        head = tarfile.TarInfo.frombuf(next_chunk, tarfile.ENCODING, 'strict')  # read the
        # https://docs.python.org/3/library/codecs.html#error-handlers
        return _FilthyTarEntry(chunk_reader, next_chunk, head, start_offset)

    def _next_extended_entry(self, chunk_reader: ChunkReader, start_offset: int) -> _FilthyTarEntry:
        """Iterate over all entries in source. Extended headers will be combined and only "regular" entries will be
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

    def iterate_entries(self, data: IOProducer) -> typing.Generator[DecentTarEntry, None, None]:
        """Yield information about inner files
        """

        with contextlib.suppress(StopIteration):
            chunk_reader = ChunkReader(data, tarfile.BLOCKSIZE, strict_mode=True)
            offset = 0
            while True:
                filthy_entry = self._next_extended_entry(chunk_reader, offset)
                previous_entry = DecentTarEntry(
                    filthy_entry.parsed_info, chunk_reader, offset, len(filthy_entry.binary_info)
                )
                yield previous_entry

                if not previous_entry.is_wasted():
                    raise RuntimeError('You must read data from previous entry before requesting a next one')

                offset += len(filthy_entry.binary_info)
                offset += (filthy_entry.parsed_info.size // tarfile.BLOCKSIZE)

                if (filthy_entry.parsed_info.size % tarfile.BLOCKSIZE) != 0:
                    offset += tarfile.BLOCKSIZE


class _PartedTarWriter:
    """ This class helps to write tar archives with dynamic contents and remote locations
    """

    @dataclasses.dataclass
    class _DirtyCachePage:
        """ This is a fixed-length chunk (page) that hold some data. This includes a data that can not be written at
        the moment, but also includes a normal data that precedes or follows a dirty entry in order to fulfill the
        fixed size
        """
        index: int                       # sequential number of fixed-length part
        data: bytes                      # fixed-length data
        linked_entries: typing.Set[int]  # id of the _DirtyEntry

    @dataclasses.dataclass
    class _DirtyEntry:
        """ This class describes a data inside a _PartedTarWriter._DirtyCachePage that can not be written at the moment.
        Instead of immediate writing, this entry will be stored inside a _DirtyCachePage and will be waiting for
        following updates
        """

        page_index: int  # sequential number of fixed-length part, same as the _DirtyCachePage.index (if data is split
        # across different pages, then this value must have the very first page)
        offset: int      # starting position of this entry inside a page
        length: int      # data size

    class _Cache:
        """ This class helps to postpone some "dirty" data chunks and write them later
        """
        # TODO: this memory routine looks slowly, may be it will perform better with memory view or with something else

        def __init__(self, part_size: int):
            """ Create a cache

            :param part_size: size of the single chunk (page)
            """
            self.__part_size = part_size
            self.__part_number = 0
            self.__flushed_bytes = 0
            self.__cache = b''

            self.__cleaned_pages: typing.List[_PartedTarWriter._DirtyCachePage] = list()
            self.__dirty_pages: typing.List[_PartedTarWriter._DirtyCachePage] = list()
            self.__dirty_entries_number = 0
            self.__dirty_entries: typing.Dict[int, _PartedTarWriter._DirtyEntry] = dict()

        def __iadd__(self, other: bytes) -> '_PartedTarWriter._Cache':
            """ Append clean data to this cache
            """

            if self.__dirty_pages:
                last_dirty_page = self.__dirty_pages[-1]
                dirty_cache_delta = len(last_dirty_page.data) % self.__part_size

                if dirty_cache_delta:
                    extra_bytes = self.__part_size - dirty_cache_delta
                    last_dirty_page.data += other[:extra_bytes]
                    other = other[extra_bytes:]

                    self.__flush_dirty_pages()

            if other:
                self.__cache += other
            return self

        def flushed_bytes(self) -> int:
            """ Return number of bytes that was flushed through this cache
            """
            return self.__flushed_bytes

        def cached_size(self) -> int:
            """ Return number of unflushed bytes
            """
            dirty_pages_cache = sum((len(x.data) for x in self.__dirty_pages))
            return dirty_pages_cache + len(self.__cache)

        def flush_cache(self, with_final_chunk: bool = False) -> typing.Generator[typing.Tuple[bytes, int], None, None]:
            """ Checkout internal cache and yield fixed-length chunk (pages)

            :param with_final_chunk: whether it is the end and the last chunks should be yielded. The last chunk
            may be smaller. All the dirty entries must be fixed before this value is set to True
            """

            for page in self.__cleaned_pages:
                assert(len(page.data) == self.__part_size)
                yield page.data, page.index
            self.__cleaned_pages.clear()

            while len(self.__cache) >= self.__part_size:
                self.__flushed_bytes += self.__part_size
                yield self.__cache[:self.__part_size], self.__part_number
                self.__part_number += 1
                self.__cache = self.__cache[self.__part_size:]

            if with_final_chunk:
                if self.__dirty_pages:
                    assert(not self.__cache)
                    assert(len(self.__dirty_pages) == 1)

                    self.__flushed_bytes += len(self.__dirty_pages[0].data)
                    yield self.__dirty_pages[0].data, self.__dirty_pages[0].index
                    self.__dirty_pages.clear()

                elif self.__cache:
                    assert(not self.__dirty_pages)

                    self.__flushed_bytes += len(self.__cache)
                    yield self.__cache, self.__part_number
                    self.__part_number += 1
                    self.__cache = b''

        def dirty_entry(self, dirty_data: bytes) -> int:
            """ Append dirty entry to this cache and return its identifier

            :param dirty_data: a dirty data that will be fixed later
            """

            entry_index = self.__dirty_entries_number
            header_len = len(dirty_data)

            if self.__dirty_pages:
                last_dirty_page = self.__dirty_pages[-1]
                dirty_cache_delta = len(last_dirty_page.data) % self.__part_size

                if dirty_cache_delta:
                    assert(not self.__cache)

                    extra_bytes = self.__part_size - dirty_cache_delta
                    offset = len(last_dirty_page.data)
                    last_dirty_page.data += dirty_data[:extra_bytes]
                    dirty_data = dirty_data[extra_bytes:]
                    last_dirty_page.linked_entries.add(entry_index)

                    self.__dirty_entries[entry_index] = _PartedTarWriter._DirtyEntry(last_dirty_page.index, offset, header_len)

            if dirty_data:
                offset = len(self.__cache)
                assert(offset < self.__part_size)

                next_dirty_cache = self.__cache + dirty_data
                self.__cache = b''
                self.__dirty_entries[entry_index] = _PartedTarWriter._DirtyEntry(self.__part_number, offset, header_len)

                while len(next_dirty_cache):
                    self.__dirty_pages.append(
                        _PartedTarWriter._DirtyCachePage(
                            self.__part_number, next_dirty_cache[:self.__part_size], {entry_index,},
                        )
                    )
                    self.__part_number += 1
                    next_dirty_cache = next_dirty_cache[self.__part_size:]

            self.__dirty_entries_number += 1
            return entry_index

        def fix_dirty_entry(self, dirty_entry_index: int, patched_data: bytes) -> None:
            """ Fix a data that was previously marked as dirty. This patch must be the same length as a previous data
            (no more no less). This method also cleans dirty pages (if possible)

            :param dirty_entry_index: identifier of the dirty entry
            """

            entry_info = self.__dirty_entries[dirty_entry_index]
            assert(entry_info.length == len(patched_data))

            page_found = False
            for dirty_page in self.__dirty_pages:
                if dirty_page.index == entry_info.page_index:
                    page_found = True

                    page_fix = patched_data[:self.__part_size - entry_info.offset]
                    patched_data = patched_data[len(page_fix):]
                    dirty_page.data = dirty_page.data[:entry_info.offset] + page_fix + dirty_page.data[(entry_info.offset + len(page_fix)):]
                    dirty_page.linked_entries.remove(dirty_entry_index)

                    pages_span = 0
                    while patched_data:
                        pages_span += 1

                        span_page_found = False
                        for span_dirty_page in self.__dirty_pages:
                            if span_dirty_page.index == (dirty_page.index + pages_span):
                                span_page_found = True

                                page_fix = patched_data[:self.__part_size]
                                patched_data = patched_data[len(page_fix):]
                                span_dirty_page.data = page_fix + span_dirty_page.data[len(page_fix):]

                        assert(span_page_found)

                    break

            assert(page_found)
            self.__flush_dirty_pages()

        def __flush_dirty_pages(self) -> None:
            """ Try to "clean" dirty pages (if possible), so make pages that are no longer dirty to become ready for
            the next flush
            """
            still_dirty_pages = []

            for dirty_page in self.__dirty_pages:
                if not dirty_page.linked_entries and len(dirty_page.data) == self.__part_size:
                    self.__cleaned_pages.append(dirty_page)
                else:
                    still_dirty_pages.append(dirty_page)

            self.__dirty_pages = still_dirty_pages

    def __init__(
        self, part_size: int, sources: typing.Iterable[typing.Union[StaticTarEntryProto, DynamicTarEntryProto]]
    ) -> None:
        """ Create a new writer

        :param part_size: fixed part size to yield
        :param sources: list of entries to archive
        """

        self.__part_size = part_size
        self.__sources = sources

        self.__generator = self.__parts_generator()

    def __parts_generator(self) -> typing.Generator[typing.Tuple[bytes, int], None, None]:
        """ Yield parts (tuple of fixed length bytes and part number)
        """

        cache = _PartedTarWriter._Cache(self.__part_size)

        for source in self.__sources:
            if isinstance(source, StaticTarEntryProto):
                for chunk in source.entry():
                    cache += chunk

                    yield from cache.flush_cache()
            else:
                assert(isinstance(source, DynamicTarEntryProto))

                tar_header = source.tar_info(MAX_DYNAMIC_FILE_SIZE)
                dirty_entry = cache.dirty_entry(tar_header)

                data_size = 0
                for chunk in source.data():
                    data_size += len(chunk)
                    cache += chunk
                    yield from cache.flush_cache()

                # TODO: rewrite common alignment code!
                extra_entry_bytes = data_size % tarfile.BLOCKSIZE
                entry_delta = (tarfile.BLOCKSIZE - extra_entry_bytes) if extra_entry_bytes else 0
                if entry_delta:
                    cache += (b'\0' * entry_delta)

                patched_tar_header = source.tar_info(data_size, len(tar_header))
                assert(len(tar_header) == len(patched_tar_header))
                cache.fix_dirty_entry(dirty_entry, patched_tar_header)
                yield from cache.flush_cache()

        # TODO: rewrite common alignment code!
        extra_bytes = (cache.flushed_bytes() + cache.cached_size()) % tarfile.RECORDSIZE
        delta = (tarfile.RECORDSIZE - extra_bytes) if extra_bytes else 0
        delta += tarfile.RECORDSIZE
        cache += (b'\0' * delta)
        yield from cache.flush_cache(with_final_chunk=True)

    def __iter__(self) -> '_PartedTarWriter':
        """ Make this object an iterator
        """
        return self

    def __next__(self) -> typing.Tuple[bytes, int]:
        """ Return next part (fixed length bytes and part number)
        """
        return next(self.__generator)


class TarArchive(_TarPaddingGenerator):
    """This class helps to save a single tar archive or helps to read it
    """

    def __init__(self) -> None:
        """Create a new tar archive writer
        """
        _TarPaddingGenerator.__init__(self, aligned_to=tarfile.RECORDSIZE, extra_padding=True)

    def static_archive(self, sources: typing.Iterable[StaticTarEntryProto]) -> IOGenerator:
        """Yield data that may be saved as a tar archive.

        :param sources: archive entries
        """

        def entries() -> IOGenerator:
            for s in sources:
                yield from s.entry()

        yield from self._write(entries())

    @verify_value(destination=lambda x: x.seekable())
    async def dynamic_archive_to_file(
        self,
        destination: typing.IO[bytes],
        sources: typing.Iterable[typing.Union[StaticTarEntryProto, DynamicTarEntryProto]],
        write_throttling: typing.Optional[int] = None
    ) -> None:
        """Save data as a tar archive to IO-object (this object must be seekable)

        :param destination: destination file
        :param sources: archive entries
        :param write_throttling: whether to throttle at saving (number of bytes per second)
        """
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

    async def dynamic_archive_to_uri(
        self,
        destination: URI,
        sources: typing.Iterable[typing.Union[StaticTarEntryProto, DynamicTarEntryProto]],
        write_throttling: typing.Optional[int] = None
    ) -> None:
        # TODO: it should not be async with 5MB chunks!
        """Save data as a tar archive to IO-object (this object must be seekable)

        :param destination: destination file
        :param sources: archive entries
        :param write_throttling: whether to throttle at saving (number of bytes per second)  # TODO: implement!
        """

        file_name, client = IOVirtualClient.create_client_w_file_path(destination)

        if not iscapable(client, IOClientProto.upload_by_part):
            raise ValueError(
                f'The client from the "{str(destination)}" does not implement the "upload_by_part" capability'
            )

        part_size = (5 * (1024 ** 2))  # TODO: make a constant! Or input parameter, as for now this is a minimal
        # chunk size for S3

        with client.upload_by_part(file_name, part_size) as uploader:
            for data, part_number in _PartedTarWriter(part_size, sources):
                uploader.upload_part(data, part_number)

    @staticmethod
    @verify_value(source=lambda x: x.seekable())
    def extract_from_file(source: typing.IO[bytes], filename: str) -> IOGenerator:
        """Extract data from an archive

        :param source: tar-data
        :param filename: name of a file to retrieve from archive
        """

        start_pos = source.tell()

        with tarfile.open(fileobj=source) as tar:
            tar_info = tar.getmember(filename)
            file_size = tar_info.size
            source.seek(start_pos + tar_info.offset_data, os.SEEK_SET)

            if file_size:  # not empty file
                yield from IOThrottler.sync_reader(source, read_size=file_size)

        source.seek(start_pos, os.SEEK_SET)

    @staticmethod
    def extract_from_uri(source: URI, filename: str) -> IOGenerator:
        """Extract data from an archive

        :param source: a path to a file
        :param filename: name of a file to retrieve from archive
        """
        # TODO: implement!
        raise NotImplementedError('Not ready!')


class TarArchiveReaderProto(metaclass=ABCMeta):
    """ Prototype for reader that is able to process tar-archive
    """

    @abstractmethod
    def entries(self) -> typing.Generator[DecentTarEntry, None, None]:
        """ Read data and yield information about inner files. Entries are returned one by one. Each entry must
        be read with the :meth:`.DecentTarEntry.data` method before the request for the next entry.
        """
        raise NotImplementedError('This method is abstract')

    @abstractmethod
    def inner_descriptors(self) -> typing.Generator[tarfile.TarInfo, None, None]:
        """ Yield information about inner files. Entries are returned one by one
        """
        raise NotImplementedError('This method is abstract')


class IOTarReader(TarArchiveReaderProto):
    """ This reader implementation reads data sequentially so it is more robust but has huge performance penalties
    for the :meth:`TarArchiveReaderProto.inner_descriptors` method implementation
    """

    def __init__(self, source: IOProducer):
        """ This implementation reads tar-archive from :class:`.IOProducer`

        :param source: tar-archive to read
        """
        TarArchiveReaderProto.__init__(self)
        self.__source = source

    def entries(self) -> typing.Generator[DecentTarEntry, None, None]:
        """ The :meth:`.TarArchiveReaderProto.entries` method implementation.
        """
        yield from _TarReader().iterate_entries(self.__source)

    def inner_descriptors(self) -> typing.Generator[tarfile.TarInfo, None, None]:
        """The :meth:`.TarArchiveReaderProto.inner_descriptors` method implementation."""
        for i in _TarReader().iterate_entries(self.__source):
            yield i.tar_info()
            for _ in i.data():
                pass


class URITarReader(TarArchiveReaderProto):
    """ Read a file with the :class:`.IOClientProto` client
    """

    def __init__(self, file_uri: URI) -> None:
        TarArchiveReaderProto.__init__(self)
        self.__uri = file_uri
        self.__file_name, self.__client = IOVirtualClient.create_client_w_file_path(self.__uri)

        if not iscapable(self.__client, IOClientProto.receive_file):
            raise ValueError(
                f'The client from the "{str(self.__uri)}" does not implement the "receive_file" capability'
            )

        if not iscapable(self.__client, IOClientProto.receive_file_with_offset):
            raise ValueError(
                f'The client from the "{str(self.__uri)}" does not implement the "receive_file_with_offset" capability'
            )

    def entries(self) -> typing.Generator[DecentTarEntry, None, None]:
        data = self.__client.receive_file(self.__file_name)
        yield from _TarReader().iterate_entries(data)

    def inner_descriptors(self) -> typing.Generator[tarfile.TarInfo, None, None]:
        offset = 0

        with contextlib.suppress(StopIteration):
            while True:
                data = self.__client.receive_file_with_offset(self.__file_name, offset)

                tar_entry = next(_TarReader().iterate_entries(data))
                tar_info = tar_entry.tar_info()
                yield tar_info

                offset += tar_entry.head_offset() + tar_entry.head_size()
                offset += (tar_info.size // tarfile.BLOCKSIZE)

                if (tar_info.size % tarfile.BLOCKSIZE) != 0:
                    offset += tarfile.BLOCKSIZE
