# -*- coding: utf-8 -*-
# pyknic/lib/io/tar/writers.py
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

import dataclasses
import datetime
import grp
import os
import pathlib
import pwd
import tarfile
import time
import typing

from abc import ABCMeta, abstractmethod

from pyknic.lib.capability import iscapable
from pyknic.lib.io import IOGenerator, IOProducer
from pyknic.lib.io.aio_wrapper import IOThrottler, cg
from pyknic.lib.io.clients.proto import IOClientProto
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


class TarWriterEntryProto(metaclass=ABCMeta):
    """This class describes tar entry

    :note: please note the MAX_DYNAMIC_FILE_SIZE
    """

    @abstractmethod
    def tar_info(self) -> tarfile.TarInfo:
        """ Return tar header that represents this entry, please note that the size may be not set since it will
        be calculated later automatically
        """
        raise NotImplementedError('This method is abstract')

    @abstractmethod
    def data(self) -> IOGenerator:
        """ Return data of this entry
        """
        raise NotImplementedError('This method is abstract')


class _TarInfoGenerator:
    """This class helps to generate a custom tar info.
    """

    @staticmethod
    def tar_info_pax_padding(tar_info: tarfile.TarInfo, expected_size: int) -> tarfile.TarInfo:
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

    @staticmethod
    def custom_tar_info(
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
        """Generate meta-info for a single file inside archive.

        :param filename: filename of an inner file.
        :param size: size of file (zero by default).
        :param mtime: file modification time (is now by default).
        :param mode: file mode (0440 by default).
        :param uid: file UID (current process user is used by default).
        :param gid: file GID (current process group is used by default).
        :param uname: username related to uid.
        :param gname: group name related to gid.
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

        return tar_info

    @staticmethod
    def tar_info_by_file(filename: typing.Union[str, pathlib.Path]) -> tarfile.TarInfo:
        """Retrieve meta-info by a real file

        :param filename: file name which meta-info should be retrieved
        """
        # TODO: filename related to some directory?!
        tar_file = tarfile.TarFile('/dev/zero', mode='w')  # TODO: it seams bogus
        tar_info = tar_file.gettarinfo(filename)

        if tar_info.name.startswith('/'):
            raise ValueError('Tar entries should not have absolute path because of possible tar bomb')

        return tar_info


class TarFileEntry(TarWriterEntryProto):
    """This class helps to save single a file (directory) inside a tar archive.
    """

    def __init__(self, file_path: str):
        TarWriterEntryProto.__init__(self)
        self.__file_path = file_path
        self.__cached_tar_info: typing.Optional[tarfile.TarInfo] = None

    def tar_info(self) -> tarfile.TarInfo:
        """ :meth:`.TarWriterEntryProto.tar_info` implementation
        """
        if self.__cached_tar_info is None:
            self.__cached_tar_info = _TarInfoGenerator.tar_info_by_file(self.__file_path)
            self.__cached_tar_info.size = -1  # forces size to recalculate

        assert(self.__cached_tar_info)
        return self.__cached_tar_info

    def data(self) -> IOGenerator:
        """ :meth:`.TarWriterEntryProto.data` implementation
        """

        if pathlib.Path(self.__file_path).is_file():
            with open(self.__file_path, 'rb') as f:
                yield from IOThrottler.sync_reader(f)


class TarDynamicEntry(TarWriterEntryProto):
    """This class helps to save a dynamic data from generator inside a tar archive.
    """

    def __init__(
        self,
        source: IOProducer,
        file_path: str,
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
        :param file_path: name of an inner file

        :param mtime: file modification time (is now by default)
        :param mode: file mode (0440 by default)
        :param uid: file UID (current process user is used by default)
        :param gid: file GID (current process group is used by default)
        :param uname: username related to uid
        :param gname: group name related to gid        """
        TarWriterEntryProto.__init__(self)

        if file_path.startswith('/'):
            raise ValueError('File path must be relative')

        self.__tar_info = _TarInfoGenerator.custom_tar_info(
            file_path,
            size=-1,
            mtime=mtime,
            mode=mode,
            uid=uid,
            gid=gid,
            uname=uname,
            gname=gname,
        )

        self.__source = source

    def tar_info(self) -> tarfile.TarInfo:
        """ :meth:`.TarWriterEntryProto.tar_info` implementation
        """
        return self.__tar_info

    def data(self) -> IOGenerator:
        """ :meth:`.TarWriterEntryProto.data` implementation
        """
        yield from self.__source


class TarArchiveWriterProto(metaclass=ABCMeta):
    """ This is a prototype for a custom tar archive writer
    """

    @abstractmethod
    def archive(self, sources: typing.Iterable[TarWriterEntryProto]) -> None:
        """ Saves the specified entries to a tar archive

        :param sources: list of tar entries to save
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

    def write(self, data: IOProducer) -> IOGenerator:
        """This processor writes data and required padding

        :param data: data to write
        """
        for block in data:
            self.__counter += len(block)
            yield block

        delta = self.padding_length(self.__counter)
        yield (b'\0' * delta) if delta else b''

    def padding_length(self, counter: int) -> int:
        """ Calculate padding length for the specified counter

        :param counter: base length to calculate padding from
        """
        extra_bytes = counter % self.__aligned_to
        delta = (self.__aligned_to - extra_bytes) if extra_bytes else 0
        if self.__extra_padding:
            delta += self.__aligned_to

        return delta


class IOTarArchiveWriter(TarArchiveWriterProto):
    """ This :class:`.TarArchiveWriterProto` implementation writes to a custom file-objects
    """

    @verify_value(destination=lambda x: x.seekable())
    def __init__(self, destination: typing.IO[bytes], write_throttling: typing.Optional[int] = None):
        """ Create a new tar-writer

        :param destination: destination file-object to write to
        :param write_throttling: bytes per second rate to write with
        """

        TarArchiveWriterProto.__init__(self)

        self.__destination = destination
        self.__write_throttling = write_throttling

    def __entry_writer(self, entry: TarWriterEntryProto) -> IOGenerator:
        """ Generate data for a single entry

        :param entry: entry to write
        """

        def data_generator() -> IOGenerator:
            start_pos = self.__destination.tell()

            tar_info = entry.tar_info()
            tar_info.size = MAX_DYNAMIC_FILE_SIZE
            pre_gen_info = tar_info.tobuf()
            yield pre_gen_info

            data_size = 0
            for chunk in entry.data():
                data_size += len(chunk)

                if data_size > MAX_DYNAMIC_FILE_SIZE:
                    raise ValueError('Are you saving the universe?!')

                yield chunk

            end_pos = self.__destination.tell()
            tar_info.size = data_size
            tar_info = _TarInfoGenerator.tar_info_pax_padding(tar_info, len(pre_gen_info))
            patched_tar_info = tar_info.tobuf()
            assert(len(pre_gen_info) == len(patched_tar_info))

            self.__destination.seek(start_pos, os.SEEK_SET)
            self.__destination.write(patched_tar_info)
            self.__destination.seek(end_pos, os.SEEK_SET)

        padding_generator = _TarPaddingGenerator(aligned_to=tarfile.BLOCKSIZE)
        yield from padding_generator.write(data_generator())

    def archive(self, sources: typing.Iterable[TarWriterEntryProto]) -> None:
        """ :meth:`.TarArchiveWriterProto.archive` implementation
        """

        self.__destination.seek(0)
        self.__destination.truncate()

        def entries() -> IOGenerator:
            for s in sources:
                yield from self.__entry_writer(s)

        padding_generator = _TarPaddingGenerator(aligned_to=tarfile.RECORDSIZE, extra_padding=True)

        cg(
            IOThrottler.sync_writer(
                padding_generator.write(
                    entries()
                ),
                self.__destination,
                throttling=self.__write_throttling
            )
        )


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
        data: bytearray                  # fixed-length data
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

        def __init__(self, part_size: int):
            """ Create a cache

            :param part_size: size of the single chunk (page)
            """
            self.__part_size = part_size
            self.__part_number = 0
            self.__flushed_bytes = 0
            self.__cache = bytearray()

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

        def flush_cache(
            self, with_final_chunk: bool = False
        ) -> typing.Generator[typing.Tuple[bytearray, int], None, None]:
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
                    self.__cache = bytearray()

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

                    self.__dirty_entries[entry_index] = _PartedTarWriter._DirtyEntry(
                        last_dirty_page.index, offset, header_len
                    )

            if dirty_data:
                offset = len(self.__cache)
                assert(offset < self.__part_size)

                next_dirty_cache = self.__cache + dirty_data
                self.__cache = bytearray()
                self.__dirty_entries[entry_index] = _PartedTarWriter._DirtyEntry(self.__part_number, offset, header_len)

                while len(next_dirty_cache):
                    self.__dirty_pages.append(
                        _PartedTarWriter._DirtyCachePage(
                            self.__part_number,
                            next_dirty_cache[:self.__part_size],
                            {entry_index, }
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
            :param patched_data: updated data
            """

            entry_info = self.__dirty_entries[dirty_entry_index]
            assert(entry_info.length == len(patched_data))

            page_found = False
            for dirty_page in self.__dirty_pages:
                if dirty_page.index == entry_info.page_index:
                    page_found = True

                    page_fix = patched_data[:self.__part_size - entry_info.offset]
                    patched_data = patched_data[len(page_fix):]

                    dirty_page.data = (
                        dirty_page.data[:entry_info.offset] +
                        page_fix +
                        dirty_page.data[(entry_info.offset + len(page_fix)):]
                    )

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
                                span_dirty_page.data = bytearray(page_fix) + span_dirty_page.data[len(page_fix):]

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
        self, part_size: int, sources: typing.Iterable[TarWriterEntryProto]
    ) -> None:
        """ Create a new writer

        :param part_size: fixed part size to yield
        :param sources: list of entries to archive
        """

        self.__part_size = part_size
        self.__sources = sources

        self.__generator = self.__parts_generator()

    def __parts_generator(self) -> typing.Generator[typing.Tuple[bytearray, int], None, None]:
        """ Yield parts (tuple of fixed length bytes and part number)
        """

        cache = _PartedTarWriter._Cache(self.__part_size)

        for source in self.__sources:
            tar_header = source.tar_info()
            tar_header.size = MAX_DYNAMIC_FILE_SIZE
            binary_tar_header = tar_header.tobuf()

            dirty_entry = cache.dirty_entry(binary_tar_header)

            data_size = 0
            for chunk in source.data():
                data_size += len(chunk)

                if data_size > MAX_DYNAMIC_FILE_SIZE:
                    raise ValueError('Are you saving the universe?!')

                cache += chunk
                yield from cache.flush_cache()

            entry_padding = _TarPaddingGenerator(tarfile.BLOCKSIZE).padding_length(data_size)
            if entry_padding:
                cache += (b'\0' * entry_padding)

            tar_header.size = data_size
            tar_header = _TarInfoGenerator.tar_info_pax_padding(tar_header, len(binary_tar_header))
            patched_tar_header = tar_header.tobuf()
            assert(len(binary_tar_header) == len(patched_tar_header))
            cache.fix_dirty_entry(dirty_entry, patched_tar_header)
            yield from cache.flush_cache()

        padding_generator = _TarPaddingGenerator(aligned_to=tarfile.RECORDSIZE, extra_padding=True)
        tar_padding = padding_generator.padding_length(cache.flushed_bytes() + cache.cached_size())
        cache += (b'\0' * tar_padding)

        yield from cache.flush_cache(with_final_chunk=True)

    def __iter__(self) -> '_PartedTarWriter':
        """ Make this object an iterator
        """
        return self

    def __next__(self) -> typing.Tuple[bytearray, int]:
        """ Return next part (fixed length bytes and part number)
        """
        return next(self.__generator)


class ClientTarArchiveWriter(TarArchiveWriterProto):
    """ This :class:`.TarArchiveWriterProto` implementation writes to a file with a custom IO-client
    """

    @verify_value(client=lambda x: iscapable(x, IOClientProto.upload_by_part))
    def __init__(
        self,
        client: IOClientProto,
        destination_file: str,
        write_throttling: typing.Optional[int] = None,
        part_size: typing.Optional[int] = None
    ) -> None:
        """Save data as a tar archive to IO-object (this object must be seekable)

        :param client: an IO-client to use
        :param destination_file: file to write archive to
        :param write_throttling: whether to throttle at saving (number of bytes per second)
        :param part_size: number of bytes each chunk should have for a single write request. Please note, that
        S3 requires part_size to be not less than 5MB, so this value is used as default one
        """
        TarArchiveWriterProto.__init__(self)

        self.__client = client
        self.__destination_file = destination_file
        self.__write_throttling = write_throttling
        self.__part_size = (5 * (1024 ** 2)) if part_size is None else part_size

    def archive(self, sources: typing.Iterable[TarWriterEntryProto]) -> None:
        """ :meth:`.TarArchiveWriterProto.archive` implementation
        """

        throttler = IOThrottler(throttling=self.__write_throttling)

        with self.__client.upload_by_part(self.__destination_file, self.__part_size) as uploader:
            for data, part_number in _PartedTarWriter(self.__part_size, sources):
                throttler += len(data)
                uploader.upload_part(data, part_number)
                time.sleep(throttler.pause())


class TarFileGenerator:
    """ This class helps to generate a custom tar-data from static files

    :note: It is important that the file size must not be changed during archiving!
    """

    @staticmethod
    def tar(files: typing.Iterable[str]) -> IOGenerator:
        """ Archive files and return data-flow that represents tar-file
        """
        file_padding = _TarPaddingGenerator(aligned_to=tarfile.RECORDSIZE, extra_padding=True)

        def tar_entry(file: str) -> IOGenerator:
            tar_info = _TarInfoGenerator.tar_info_by_file(file)
            yield tar_info.tobuf()
            if tar_info.size > 0 and pathlib.Path(file).is_file():
                with open(file, 'rb') as file_obj:
                    yield from IOThrottler.sync_reader(file_obj, read_size=tar_info.size)

        def all_entries() -> IOGenerator:
            for f in files:
                entry_padding = _TarPaddingGenerator(aligned_to=tarfile.BLOCKSIZE)
                yield from entry_padding.write(tar_entry(f))

        yield from file_padding.write(all_entries())
