# -*- coding: utf-8 -*-

import asyncio
import base64
import contextlib
import io
import os
import pathlib
import typing

import pytest

from pyknic.lib.io.aio_wrapper import cg, IOThrottler
from pyknic.lib.backup.archive_v1 import ArchiveInnerFiles, ArchiveV1HeaderMeta, ArchiveType, CompressionMode
from pyknic.lib.backup.archive_v1 import ArchiveV1MetaCipher, ArchiveV1PBKDF, BackupArchiveV1, HashMethod
from pyknic.lib.io.tar import TarArchive, TarInnerDynamicGenerator

from fixtures.asyncio import pyknic_async_test

# TODO: test throttling
# TODO: test bash scripts!


class TestArchiveInnerFiles:

    def test_backup_file(self) -> None:
        header_meta = ArchiveV1HeaderMeta(
            type=ArchiveType.io_archive,
            compression=CompressionMode.no_compression
        )
        assert(ArchiveInnerFiles.backup_file(header_meta) == 'backup')

        header_meta = ArchiveV1HeaderMeta(
            type=ArchiveType.io_archive,
            compression=CompressionMode.gzip,
            cipher=ArchiveV1MetaCipher(
                pbkdf=ArchiveV1PBKDF(
                    salt=base64.b64encode(b'bad salt'),
                    iterations=1,
                    hash_name='SHA1'
                ),
                cipher_name='AES',
                decryptor_info=None
            )
        )
        assert(ArchiveInnerFiles.backup_file(header_meta) == 'backup.gz.enc')

        header_meta = ArchiveV1HeaderMeta(
            type=ArchiveType.file_archive,
            compression=CompressionMode.bzip2
        )
        assert(ArchiveInnerFiles.backup_file(header_meta) == 'backup.tar.bz2')

        header_meta = ArchiveV1HeaderMeta(
            type=ArchiveType.file_archive,
            compression=CompressionMode.lzma,
            cipher=ArchiveV1MetaCipher(
                pbkdf=ArchiveV1PBKDF(
                    salt=base64.b64encode(b'bad salt'),
                    iterations=1,
                    hash_name='SHA1'
                ),
                cipher_name='AES',
                decryptor_info=None
            )
        )
        assert(ArchiveInnerFiles.backup_file(header_meta) == 'backup.tar.xz.enc')


class TestBackupArchiveV1:

    @pyknic_async_test
    async def test_plain(self, module_event_loop: asyncio.AbstractEventLoop, tmp_path: pathlib.Path) -> None:
        test_data = io.BytesIO(b'Test data')
        archive = BackupArchiveV1()

        tar_archive_file = tmp_path / "archive.tar"

        with tar_archive_file.open('wb') as f:
            await archive.backup_io(IOThrottler.sync_reader(test_data), f)

        with tar_archive_file.open('rb') as f:
            assert(test_data.getvalue() == b''.join(BackupArchiveV1.extract_data(f)))

    @pyknic_async_test
    @pytest.mark.parametrize(
        'hash_algos, compression, encryption_key',
        [
            [None, CompressionMode.no_compression, None],
            [[HashMethod.sha256, HashMethod.blake2b_64], CompressionMode.no_compression, None],
            [[HashMethod.sha256, HashMethod.blake2b_64], CompressionMode.gzip, None],
            [[HashMethod.sha256, HashMethod.blake2b_64], CompressionMode.no_compression, 'foobarfoobarfoobarfoobar'],
            [[HashMethod.sha256, HashMethod.blake2b_64], CompressionMode.gzip, 'foobarfoobarfoobarfoobar'],
            [[HashMethod.sha256, HashMethod.blake2b_64], CompressionMode.no_compression, 'foobarfoobarfoobarfoobar'],
            [None, CompressionMode.gzip, None],
            [None, CompressionMode.gzip, 'foobarfoobarfoobarfoobar'],
            [None, CompressionMode.no_compression, 'foobarfoobarfoobarfoobar'],
        ]
    )
    async def test_empty_file(
        self,
        monkeypatch: pytest.MonkeyPatch,
        hash_algos: typing.Optional[typing.List[HashMethod]],
        compression: CompressionMode,
        encryption_key: typing.Optional[str],
        module_event_loop: asyncio.AbstractEventLoop,
        tmp_path: pathlib.Path
    ) -> None:
        archive = BackupArchiveV1(
            hash_algorithms=hash_algos,
            compression=compression,
            encryption_key=encryption_key
        )

        tar_archive_file = tmp_path / "archive.tar"

        with (tmp_path / "sample").open('wb') as f:
            f.write(b'')

        with tar_archive_file.open('wb') as f:
            monkeypatch.chdir(str(tmp_path))
            await archive.backup_files(['sample'], f)  # just check that there is no error

    @pyknic_async_test
    @pytest.mark.parametrize(
        'hash_algos, compression, encryption_key',
        [
            [None, CompressionMode.no_compression, None],
            [[HashMethod.sha256, HashMethod.blake2b_64], CompressionMode.no_compression, None],
            [[HashMethod.sha256, HashMethod.blake2b_64], CompressionMode.gzip, None],
            [[HashMethod.sha256, HashMethod.blake2b_64], CompressionMode.no_compression, 'foobarfoobarfoobarfoobar'],
            [[HashMethod.sha256, HashMethod.blake2b_64], CompressionMode.gzip, 'foobarfoobarfoobarfoobar'],
            [[HashMethod.sha256, HashMethod.blake2b_64], CompressionMode.no_compression, 'foobarfoobarfoobarfoobar'],
            [None, CompressionMode.gzip, None],
            [None, CompressionMode.gzip, 'foobarfoobarfoobarfoobar'],
            [None, CompressionMode.no_compression, 'foobarfoobarfoobarfoobar'],
        ]
    )
    async def test_empty_io(
        self,
        hash_algos: typing.Optional[typing.List[HashMethod]],
        compression: CompressionMode,
        encryption_key: typing.Optional[str],
        module_event_loop: asyncio.AbstractEventLoop,
        tmp_path: pathlib.Path
    ) -> None:
        archive = BackupArchiveV1(
            hash_algorithms=hash_algos,
            compression=compression,
            encryption_key=encryption_key
        )

        tar_archive_file = tmp_path / "archive.tar"

        with tar_archive_file.open('wb') as f:
            await archive.backup_io(IOThrottler.sync_reader(io.BytesIO(b'')), f)  # just check that there is no error

    @pyknic_async_test
    async def test_extra_meta(self, module_event_loop: asyncio.AbstractEventLoop, tmp_path: pathlib.Path) -> None:
        test_data = io.BytesIO(b'Test data')
        archive = BackupArchiveV1()

        tar_archive_file = tmp_path / "archive.tar"

        with tar_archive_file.open('wb') as f:
            await archive.backup_io(IOThrottler.sync_reader(test_data), f)

        with tar_archive_file.open('rb') as f:
            header = BackupArchiveV1.extract_header_meta(f)
            assert(header.extra is None)

        extra_data = {"data": [1, 2, 3]}
        archive = BackupArchiveV1(extra_meta=extra_data)
        with tar_archive_file.open('wb') as f:
            await archive.backup_io(IOThrottler.sync_reader(test_data), f)

        with tar_archive_file.open('rb') as f:
            header = BackupArchiveV1.extract_header_meta(f)
            assert(header.extra == extra_data)

    @pyknic_async_test
    @pytest.mark.parametrize(
        'compression_mode, backup_file, reference_size',
        [
            [CompressionMode.no_compression, 'backup', 9],
            [CompressionMode.gzip, 'backup.gz', 35],
            [CompressionMode.lzma, 'backup.xz', 68],
            [CompressionMode.bzip2, 'backup.bz2', 49]
        ]
    )
    async def test_compression(
        self,
        compression_mode: CompressionMode,
        backup_file: str,
        reference_size: int,
        module_event_loop: asyncio.AbstractEventLoop,
        tmp_path: pathlib.Path
    ) -> None:
        test_data = io.BytesIO(b'Test data')
        archive = BackupArchiveV1(
            compression=compression_mode
        )

        tar_archive_file = tmp_path / "archive.tar"

        with tar_archive_file.open('wb') as f:
            await archive.backup_io(IOThrottler.sync_reader(test_data), f)

        with tar_archive_file.open('rb') as f:
            assert(test_data.getvalue() == b''.join(BackupArchiveV1.extract_data(f)))

        with open(tar_archive_file, 'rb') as f:
            assert(cg(TarArchive().extract(f, backup_file)) == reference_size)

    @pyknic_async_test
    @pytest.mark.parametrize('i', list(range(10)))  # some time this test fails
    async def test_encryption(
        self, i: int, module_event_loop: asyncio.AbstractEventLoop, tmp_path: pathlib.Path
    ) -> None:
        test_data = io.BytesIO(b'Test data')
        encryption_key = 'foobarfoobarfoobarfoobar'

        archive = BackupArchiveV1(
            encryption_key=encryption_key
        )

        tar_archive_file = tmp_path / "archive.tar"

        with tar_archive_file.open('wb') as f:
            await archive.backup_io(IOThrottler.sync_reader(test_data), f)

        with tar_archive_file.open('rb') as f:
            assert(test_data.getvalue() == b''.join(BackupArchiveV1.extract_data(f, encryption_key=encryption_key)))

        with pytest.raises(ValueError):
            with tar_archive_file.open('rb') as f:
                cg(BackupArchiveV1.extract_data(f))

        data = None
        with contextlib.suppress(RuntimeError):  # may PKCS7 error happen
            with tar_archive_file.open('rb') as f:
                data = b''.join(BackupArchiveV1.extract_data(f, encryption_key=(encryption_key + '-baaad')))

        assert(data != test_data.getvalue())

    @pyknic_async_test
    @pytest.mark.parametrize(
        'hash_algos, digests',
        [
            [[HashMethod.md5], [b'\xca\x1e\xa0,\x10\xb7\xc3\x7fB[\x9b}\xd8m^\x11']],
            [[HashMethod.sha256, HashMethod.blake2b_64], [
                b'\xe2|\x82\x14\xbe\x8b|\xf5\xbc\xcc|\x08$~<\xb0\xc1QJH\xee\x1fc\x19\x7f\xe4\xef>\xf5\x1d~o',
                b'\xca\xc2^K\x07\x9e\x8e\xa3\xb8\xd0\xb9\xab\xc5\xd7\xab\xf5\xc4i\xc4RT/\xf3\xe4\xf0R\xa9ux\xa4y\x02'
                b'\x91\xfb\xc4i9\xa5\xa9O\xb9Q\'\x8fb/\xb5\xbbm\xbdZl\x144~\xb1\xbaojK\xf7\xb8\xaa\xeb'
            ]],
        ]
    )
    async def test_digest(
        self,
        hash_algos: typing.List[HashMethod],
        digests: typing.List[bytes],
        module_event_loop: asyncio.AbstractEventLoop,
        tmp_path: pathlib.Path
    ) -> None:
        test_data = io.BytesIO(b'Test data')
        archive = BackupArchiveV1(
            hash_algorithms=hash_algos
        )

        tar_archive_file = tmp_path / "archive.tar"

        with tar_archive_file.open('wb') as f:
            await archive.backup_io(IOThrottler.sync_reader(test_data), f)

        with tar_archive_file.open('rb') as f:
            tail_meta = BackupArchiveV1.extract_tail_meta(f)
            assert({x.algorithm for x in tail_meta.hashes} == set(hash_algos))

            for i, ha in enumerate(hash_algos):
                assert([x.digest for x in tail_meta.hashes if x.algorithm == ha] == [digests[i]])

    @pyknic_async_test
    async def test_hashes_validate_chain(
        self, module_event_loop: asyncio.AbstractEventLoop, tmp_path: pathlib.Path
    ) -> None:
        test_data = io.BytesIO(b'Test data')
        archive = BackupArchiveV1(
            hash_algorithms=[HashMethod.md5, HashMethod.sha256]
        )

        tar_archive_file = tmp_path / "archive.tar"

        with tar_archive_file.open('wb') as f:
            await archive.backup_io(IOThrottler.sync_reader(test_data), f)

        with tar_archive_file.open('rb') as original_file:
            header_meta = BackupArchiveV1.extract_header_meta(original_file)
            tail_meta = BackupArchiveV1.extract_tail_meta(original_file)
            tail_meta.hashes[0].digest = (b'\x00' * len(tail_meta.hashes[0].digest))

            tar_corrupted_archive_file = tmp_path / "corrupted-archive.tar"
            with tar_corrupted_archive_file.open('wb') as corrupted_file:

                tail_file = TarInnerDynamicGenerator(
                    io.BytesIO(tail_meta.model_dump_json().encode()),
                    ArchiveInnerFiles.tail_meta.value
                )

                archive_file = TarInnerDynamicGenerator(
                    TarArchive().extract(original_file, ArchiveInnerFiles.backup_file(header_meta)),
                    ArchiveInnerFiles.backup_file(header_meta)
                )

                header_file = TarInnerDynamicGenerator(
                    TarArchive().extract(original_file, ArchiveInnerFiles.header_meta.value),
                    ArchiveInnerFiles.header_meta.value
                )

                await TarArchive().dynamic_archive(corrupted_file, [tail_file, archive_file, header_file])

        with pytest.raises(ValueError):
            # corrupted hash
            with tar_corrupted_archive_file.open('rb') as corrupted_file:
                await BackupArchiveV1.validate_archive(corrupted_file)

    @pyknic_async_test
    async def test_hashes_validate_chain_error(
        self, module_event_loop: asyncio.AbstractEventLoop, tmp_path: pathlib.Path
    ) -> None:
        test_data = io.BytesIO(b'Test data')
        archive = BackupArchiveV1()

        tar_archive_file = tmp_path / "archive.tar"

        with tar_archive_file.open('wb') as f:
            await archive.backup_io(IOThrottler.sync_reader(test_data), f)

        with pytest.raises(ValueError):
            # no digests
            with tar_archive_file.open('rb') as f:
                await BackupArchiveV1.validate_archive(f)

    @pyknic_async_test
    async def test_files(
        self,
        monkeypatch: pytest.MonkeyPatch,
        module_event_loop: asyncio.AbstractEventLoop,
        tmp_path: pathlib.Path
    ) -> None:
        test_data = b'Test data'
        archive = BackupArchiveV1()

        tar_archive_file = tmp_path / "archive.tar"

        with (tmp_path / "sample1").open('wb') as f:
            f.write(test_data + b'-sample1')

        with (tmp_path / "sample2").open('wb') as f:
            f.write(test_data + b'-sample2')

        with tar_archive_file.open('wb') as f:
            old_cwd = os.getcwd()
            monkeypatch.chdir(str(tmp_path))

            await archive.backup_files(['sample1', 'sample2'], f)

            monkeypatch.chdir(old_cwd)

        with tar_archive_file.open('rb') as af:
            destination_tar = tmp_path / "destination.tar"
            with destination_tar.open('wb') as df:
                cg(IOThrottler.sync_writer(BackupArchiveV1.extract_data(af), df))

            with destination_tar.open('rb') as df:
                assert(b''.join(TarArchive().extract(df, 'sample1')) == test_data + b'-sample1')

            with destination_tar.open('rb') as df:
                assert(b''.join(TarArchive().extract(df, 'sample2')) == test_data + b'-sample2')

    @pyknic_async_test
    async def test_corrupted_link(
        self,
        monkeypatch: pytest.MonkeyPatch,
        module_event_loop: asyncio.AbstractEventLoop,
        tmp_path: pathlib.Path
    ) -> None:
        monkeypatch.chdir(str(tmp_path))
        os.symlink('invalid-file.txt', 'link.txt')

        archive = BackupArchiveV1()

        tar_archive_file = tmp_path / "archive.tar"

        with tar_archive_file.open('wb') as f:
            await archive.backup_files(['link.txt'], f)

    @pyknic_async_test
    async def test_directory(
        self,
        monkeypatch: pytest.MonkeyPatch,
        module_event_loop: asyncio.AbstractEventLoop,
        tmp_path: pathlib.Path
    ) -> None:
        monkeypatch.chdir(str(tmp_path))
        os.mkdir('empty-dir')

        archive = BackupArchiveV1()

        tar_archive_file = tmp_path / "archive.tar"

        with tar_archive_file.open('wb') as f:
            await archive.backup_files(['empty-dir'], f)
