# -*- coding: utf-8 -*-
# pyknic/lib/backup/archive_v1.py
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

# TODO: Add snapshot support and keep original lv uuid to metadata

import asyncio
import base64
import copy
import functools
import enum
import io
import math
import time
import typing

import pydantic

from pyknic.lib.io import IOGenerator
from pyknic.lib.io.aio_wrapper import IOThrottler, chain_sync_processor, cg
from pyknic.lib.crypto.hash import __default_hashers_registry__
from pyknic.lib.io.compression import __default_io_compressors_registry__
from pyknic.lib.crypto.cipher import __default_cipher_registry__
from pyknic.lib.crypto.kdf import PBKDF2
from pyknic.lib.crypto.padding import PKCS7Padding
from pyknic.lib.io.stats import GeneratorStats
from pyknic.lib.io.tar import TarArchive, TarInnerDynamicGenerator, TarInnerFileGenerator
from pyknic.lib.verify import verify_value


@enum.unique
class ArchiveInnerFiles(enum.Enum):
    """This enum describes possible file names inside an archive.
    """
    header_meta = 'header_meta.json'  # name of file that has the :class:`.ArchiveV1HeaderMeta`
    tail_meta = 'tail_meta.json'      # name of file that has the :class:`.ArchiveV1TailMeta`

    @classmethod
    def backup_file(cls, header_meta: 'ArchiveV1HeaderMeta') -> str:
        """Return name of a file for archiving data
        """

        file_name = 'backup'

        match header_meta.type:
            case ArchiveType.io_archive:
                pass
            case ArchiveType.file_archive:
                file_name += '.tar'
            case _:
                raise ValueError(f'Unknown archive type: {header_meta.type}')

        match header_meta.compression:
            case CompressionMode.no_compression:
                pass
            case CompressionMode.gzip:
                file_name += '.gz'
            case CompressionMode.bzip2:
                file_name += '.bz2'
            case CompressionMode.lzma:
                file_name += '.xz'
            case _:
                raise ValueError(f'Unknown compression type: {header_meta.compression}')

        if header_meta.cipher:
            file_name += '.enc'

        return file_name


@enum.unique
class ArchiveType(enum.Enum):
    """This enum describes possible archive types.
    """
    io_archive = 'io_archive'      # archive has inner file that stores data as is
    file_archive = 'file_archive'  # archive has inner tar archive that consists of files from FS


@enum.unique
class CompressionMode(enum.Enum):
    """This enum describes possible compression modes. Values are pretty obvious.
    """
    no_compression = 'no_compression'
    gzip = 'gzip'
    bzip2 = 'bzip2'
    lzma = 'lzma'


@enum.unique
class HashMethod(enum.Enum):
    """This enum describes possible hashing methods. Values are pretty obvious.
    """
    blake2b_64 = 'blake2b_64'
    blake2s_32 = 'blake2s_32'
    md5        = 'md5'         # noqa: E221
    sha1       = 'sha1'        # noqa: E221
    sha224     = 'sha224'      # noqa: E221
    sha256     = 'sha256'      # noqa: E221
    sha384     = 'sha384'      # noqa: E221
    sha512     = 'sha512'      # noqa: E221
    sha512_224 = 'sha512_224'  # noqa: E221
    sha512_256 = 'sha512_256'  # noqa: E221
    sha3_224   = 'sha3_224'    # noqa: E221
    sha3_256   = 'sha3_256'    # noqa: E221
    sha3_384   = 'sha3_384'    # noqa: E221
    sha3_512   = 'sha3_512'    # noqa: E221


class ArchiveV1PBKDF(pydantic.BaseModel):
    """This model describes the way a secret key is generated.
    """
    salt: pydantic.Base64Bytes
    iterations: int
    hash_name: str


class ArchiveV1MetaCipher(pydantic.BaseModel):
    """This model describes encryption details
    """
    pbkdf: ArchiveV1PBKDF
    cipher_name: str
    decryptor_info: typing.Any


class ArchiveV1HeaderMeta(pydantic.BaseModel):
    """This model describes main archive information that may be collected before a start
    """
    version: typing.Literal['1.0.0'] = pydantic.Field(default='1.0.0', frozen=True)  # static version of this model
    type: ArchiveType                                                                # archive type -- io or file mode
    created: int = pydantic.Field(default_factory=lambda _: int(time.time()))        # when archive was created
    # as a timestamp
    compression: CompressionMode                                                     # compression details
    cipher: typing.Optional[ArchiveV1MetaCipher] = None                              # encryption details
    extra: typing.Optional[typing.Dict[str, typing.Any]] = None                      # any additional info


class ArchiveV1HashInfo(pydantic.BaseModel):
    """This model describes digest information about archived data
    """
    algorithm: HashMethod         # used algorithm
    digest: pydantic.Base64Bytes  # calculated digest


class ArchiveV1TailMeta(pydantic.BaseModel):
    """This model describes archived data
    """
    write_rate: int                                  # average data rate (bytes per second)
    hashes: typing.List[ArchiveV1HashInfo] = list()  # digests
    duration: int                                    # how long archiving process took (in seconds)


class _BackupHelper:
    """This class implements some basic logic for archiving implementation
    """

    __default_cipher__ = 'AES-256-CBC'  # default cipher that is used when encryption key is specified

    @verify_value(cipher_name=lambda x: x is None or __default_cipher_registry__.has(x))
    def __init__(
        self,
        archive_type: ArchiveType,
        encryption_key: typing.Optional[str] = None,
        cipher_name: typing.Optional[str] = None,
        compression: typing.Optional[CompressionMode] = None,
        hash_algorithms: typing.Optional[typing.Iterable[HashMethod]] = None,
        extra_meta: typing.Optional[typing.Dict[str, typing.Any]] = None
    ) -> None:
        """Create a helper

        :param archive_type: defines an archive type (just to be stored in archive meta)
        :param encryption_key: if specified then this is a base key that is used for data encryption. There will
        be no encryption of data by default.
        :param cipher_name: a cipher to use. The _BackupHelper.__default_cipher__ is used by default. For enabling
        encryption be sure that the encryption_key was set.
        :param compression: defines how archiving data will be compressed (meta-data will be always uncompressed).
        No compression by default
        :param hash_algorithms: algorithms to use for digests creation. May be used for future consistency checks.
        No digest will be provided by default.
        :param extra_meta: any additional info to store within archive meta-data
        """
        if extra_meta is not None:
            extra_meta = copy.deepcopy(extra_meta)

        self.__archive_type = archive_type
        self.__compression = compression if compression else CompressionMode.no_compression
        self.__hash_algorithms = hash_algorithms if hash_algorithms else []
        self.__extra_meta = extra_meta

        self.__cipher_data = None
        self.__cipher_encryptor = None
        if encryption_key is not None:
            if cipher_name is None:
                cipher_name = self.__default_cipher__

            cipher_cls = __default_cipher_registry__.get(cipher_name)

            pbkdf = PBKDF2(encryption_key.encode(), derived_key_length=cipher_cls.key_size())

            self.__cipher_encryptor = cipher_cls.create_encryptor(pbkdf.derived_key())
            self.__cipher_data = ArchiveV1MetaCipher(
                pbkdf=ArchiveV1PBKDF(
                    salt=base64.b64encode(pbkdf.salt()),
                    iterations=pbkdf.iterations(),
                    hash_name=pbkdf.hash_name()
                ),
                cipher_name=cipher_name,
                decryptor_info=self.__cipher_encryptor.decryptor_init_data(),
            )

        self.__digests = dict()
        for algorithm in self.__hash_algorithms:
            self.__digests[algorithm] = __default_hashers_registry__.get(algorithm.value)()

        self.__write_stats = GeneratorStats()
        self.__start_time = time.monotonic()

    def header(self) -> ArchiveV1HeaderMeta:
        """Create and return main meta-data
        """
        return ArchiveV1HeaderMeta(
            type=self.__archive_type,
            compression=self.__compression,
            cipher=self.__cipher_data,
            extra=self.__extra_meta
        )

    def tail_data(self) -> IOGenerator:
        """Create and return meta-data with some statistics and digests (if any)
        """
        hashes = [
            ArchiveV1HashInfo(algorithm=h, digest=base64.b64encode(d.digest())) for h, d in self.__digests.items()
        ]

        tail_metadata = ArchiveV1TailMeta(
            write_rate=math.ceil(self.__write_stats.rate()),
            hashes=hashes,
            duration=math.ceil(time.monotonic() - self.__start_time)
        )

        yield tail_metadata.model_dump_json().encode()

    def backup_chain(self, data: IOGenerator) -> IOGenerator:
        """Process archiving data and return encrypted and/or compressed and/or raw result (depends on arguments
        with which object was created)

        :param data: data to backup
        """
        backup_processors = []

        if self.__compression and self.__compression != CompressionMode.no_compression:
            backup_processors += [
                __default_io_compressors_registry__.get(self.__compression.value)().compress
            ]

        if self.__cipher_encryptor:
            padding_obj = PKCS7Padding()
            backup_processors += [
                functools.partial(padding_obj.pad, block_size=self.__cipher_encryptor.algo_block_size()),
                self.__cipher_encryptor.encrypt
            ]

        backup_processors += [x.update for x in self.__digests.values()]
        backup_processors += [self.__write_stats.process]

        return chain_sync_processor(data, *backup_processors)

    @classmethod
    def hashes_validate_chain(cls, tail: ArchiveV1TailMeta, data: IOGenerator) -> IOGenerator:
        """ Check that data inside archive has the correct hashes

        :param tail: meta-data with digests
        :param data: data to validate
        """

        digests = dict()
        for i in tail.hashes:
            digests[i.algorithm] = __default_hashers_registry__.get(i.algorithm.value)()

        digests_processors = [x.update for x in digests.values()]
        if len(digests_processors) == 0:
            raise ValueError('There is no digests inside archive!')

        yield from chain_sync_processor(data, *digests_processors)

        for i in tail.hashes:
            calculated_hash = digests[i.algorithm]

            if calculated_hash.digest() != i.digest:
                raise ValueError(f'The calculated hash for the "{i.algorithm.value}" did not match!')

    @classmethod
    def unarchive_chain(
        cls,
        header: ArchiveV1HeaderMeta,
        tail: ArchiveV1TailMeta,
        data: IOGenerator,
        encryption_key: typing.Optional[str] = None,
        validate_hashes: bool = False,
    ) -> IOGenerator:
        """Process archived data and return decrypted and/or uncompressed and/or raw result (depends on arguments
        with which archive was created)

        :param header: original archive header meta-data
        :param tail: original archive tail meta-data
        :param data: data to restore
        :param encryption_key: encryption key that will be used for decryption
        :param validate_hashes: whether to validate the archive hashes

        :note: there is no digest checking at the moment!
        """

        backup_processors = []

        if validate_hashes:
            backup_processors += [functools.partial(cls.hashes_validate_chain, tail)]

        if header.cipher is not None:
            if encryption_key is None:
                raise ValueError('Archive is encrypted, but no encryption key provided')

            padding_obj = PKCS7Padding()
            cipher_cls = __default_cipher_registry__.get(header.cipher.cipher_name)

            pbkdf = PBKDF2(
                encryption_key.encode(),
                derived_key_length=cipher_cls.key_size(),
                salt=header.cipher.pbkdf.salt,
                iterations_count=header.cipher.pbkdf.iterations,
                hash_fn_name=header.cipher.pbkdf.hash_name
            )

            cipher_decryptor = cipher_cls.create_decryptor(pbkdf.derived_key(), header.cipher.decryptor_info)

            backup_processors += [
                cipher_decryptor.decrypt,
                functools.partial(padding_obj.undo_pad, block_size=cipher_cls.algo_block_size()),
            ]

        if header.compression and header.compression != CompressionMode.no_compression:
            backup_processors += [
                __default_io_compressors_registry__.get(header.compression.value)().decompress
            ]

        return chain_sync_processor(data, *backup_processors)


class BackupArchiveV1:
    """This class implements public methods for backing up and restore archives
    """

    def __init__(
        self,
        hash_algorithms: typing.Optional[typing.Iterable[HashMethod]] = None,
        extra_meta: typing.Optional[typing.Dict[str, typing.Any]] = None,
        throttling: typing.Optional[int] = None,
        compression: typing.Optional[CompressionMode] = None,
        encryption_key: typing.Optional[str] = None,
        cipher_name: typing.Optional[str] = None
    ):
        """Create backup archiver

        :param hash_algorithms: algorithms to use for digests creation. May be used for future consistency checks.
        No digest will be provided by default.
        :param extra_meta: any additional info to store within archive meta-data
        :param throttling: target data-rate (bytes per second) for saving archive
        :param compression: defines how archiving data will be compressed (meta-data will be always uncompressed).
        No compression by default
        :param encryption_key: if specified then this is a base key that is used for data encryption. There will
        be no encryption of data by default.
        :param cipher_name: a cipher to use. The _BackupHelper.__default_cipher__ is used by default. For enabling
        encryption be sure that the encryption_key was set.
        """
        self.__hashes = hash_algorithms
        self.__extra_meta = extra_meta
        self.__throttling = throttling
        self.__compression = compression
        self.__encryption_key = encryption_key
        self.__cipher_name = cipher_name

    async def __backup(
        self, archive_type: ArchiveType, data_reader: IOGenerator, destination: typing.IO[bytes]
    ) -> None:
        """This method wraps backup routine

        :param archive_type: type of archive to create
        :param data_reader: data to backup
        :param destination: file target archive to write to
        """
        helper = _BackupHelper(
            archive_type=archive_type,
            hash_algorithms=self.__hashes,
            extra_meta=self.__extra_meta,
            compression=self.__compression,
            encryption_key=self.__encryption_key,
            cipher_name=self.__cipher_name
        )

        header = helper.header()
        header_reader = IOThrottler.sync_reader(io.BytesIO(header.model_dump_json().encode()))

        sources = [
            TarInnerDynamicGenerator(header_reader, ArchiveInnerFiles.header_meta.value),
            TarInnerDynamicGenerator(helper.backup_chain(data_reader), ArchiveInnerFiles.backup_file(header)),
            TarInnerDynamicGenerator(helper.tail_data(), ArchiveInnerFiles.tail_meta.value)
        ]

        await TarArchive().dynamic_archive(destination, sources, write_throttling=self.__throttling)

    async def backup_io(self, source: IOGenerator, destination: typing.IO[bytes]) -> None:
        """Backup dynamic data

        :param source: data to backup
        :param destination: file target archive to write to
        """
        await self.__backup(ArchiveType.io_archive, source, destination)

    async def backup_files(self, files: typing.Iterable[str], destination: typing.IO[bytes]) -> None:
        """Backup ordinary files

        :param files: files, directories, named sockets from FS to backup
        :param destination: file target archive to write to
        """
        # TODO: add note that check that there are no duplicates inside files generator

        def files_generator() -> typing.Generator[TarInnerFileGenerator, None, None]:
            for f in files:
                yield TarInnerFileGenerator(f)

        data_reader = TarArchive().static_archive(files_generator())

        await self.__backup(ArchiveType.file_archive, data_reader, destination)

    @classmethod
    def extract_header_meta(cls, archive: typing.IO[bytes]) -> ArchiveV1HeaderMeta:
        """Extract main meta-data from stored archive

        :param archive: archive to extract meta-data from
        """
        extractor = TarArchive().extract(archive, ArchiveInnerFiles.header_meta.value)
        header_buffer = io.BytesIO()
        cg(IOThrottler.sync_writer(extractor, header_buffer))

        return ArchiveV1HeaderMeta.model_validate_json(header_buffer.getvalue())

    @classmethod
    def extract_tail_meta(cls, archive: typing.IO[bytes]) -> ArchiveV1TailMeta:
        """Extract additional meta-data from stored archive

        :param archive: archive to extract meta-data from
        """
        extractor = TarArchive().extract(archive, ArchiveInnerFiles.tail_meta.value)
        header_buffer = io.BytesIO()
        cg(IOThrottler.sync_writer(extractor, header_buffer))

        return ArchiveV1TailMeta.model_validate_json(header_buffer.getvalue())

    @classmethod
    def extract_data(
        cls,
        archive: typing.IO[bytes],
        encryption_key: typing.Optional[str] = None,
        validate_hashes: bool = False,
    ) -> IOGenerator:
        """Extract data from stored archive

        :param archive: archive to extract from
        :param encryption_key: encryption key that was used for archive creation (if any)
        :param validate_hashes: whether to check hashes or not
        """
        header_meta = cls.extract_header_meta(archive)
        tail_meta = cls.extract_tail_meta(archive)
        inner_data = TarArchive().extract(archive, ArchiveInnerFiles.backup_file(header_meta))

        return _BackupHelper.unarchive_chain(
            header_meta, tail_meta, inner_data, encryption_key=encryption_key, validate_hashes=validate_hashes
        )

    @classmethod
    async def validate_archive(
        cls,
        archive: typing.IO[bytes],
        throttling: typing.Optional[int] = None
    ) -> None:
        """Validate data stored in an archive

        :param archive: archive to check
        :param throttling: bytes per second rate to read an archive
        """
        header_meta = cls.extract_header_meta(archive)
        tail_meta = cls.extract_tail_meta(archive)
        inner_data = TarArchive().extract(archive, ArchiveInnerFiles.backup_file(header_meta))

        throttler = IOThrottler(throttling=throttling)
        throttler.start()
        for chunk in _BackupHelper.hashes_validate_chain(tail_meta, inner_data):
            throttler += len(chunk)
            await asyncio.sleep(throttler.pause())
