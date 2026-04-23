# -*- coding: utf-8 -*-

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
from pyknic.lib.io.tar.writers import TarDynamicEntry, IOTarArchiveWriter
from pyknic.lib.io.tar.readers import ClientTarArchiveReader, FileObjectTarReader
from pyknic.lib.io.clients import IOVirtualClient
from pyknic.lib.uri import URI

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

    def test_plain(self, tmp_path: pathlib.Path) -> None:
        test_data = io.BytesIO(b'Test data')
        archive = BackupArchiveV1()

        tar_archive_file = tmp_path / "archive.tar"
        file_uri = URI.parse(f'file:///{str(tar_archive_file)}')

        archive.backup_io(IOThrottler.sync_reader(test_data), file_uri)

        assert(test_data.getvalue() == b''.join(BackupArchiveV1.extract_data(file_uri)))

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
    def test_empty_file(
        self,
        monkeypatch: pytest.MonkeyPatch,
        hash_algos: typing.Optional[typing.List[HashMethod]],
        compression: CompressionMode,
        encryption_key: typing.Optional[str],
        tmp_path: pathlib.Path
    ) -> None:
        archive = BackupArchiveV1(
            hash_algorithms=hash_algos,
            compression=compression,
            encryption_key=encryption_key
        )

        monkeypatch.chdir(str(tmp_path))

        with (tmp_path / "sample").open('wb') as f:
            f.write(b'')

        tar_archive_file = tmp_path / "archive.tar"
        file_uri = URI.parse(f'file:///{str(tar_archive_file)}')
        archive.backup_files(['sample'], file_uri)  # just check that there is no error

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
    def test_empty_io(
        self,
        hash_algos: typing.Optional[typing.List[HashMethod]],
        compression: CompressionMode,
        encryption_key: typing.Optional[str],
        tmp_path: pathlib.Path
    ) -> None:
        archive = BackupArchiveV1(
            hash_algorithms=hash_algos,
            compression=compression,
            encryption_key=encryption_key
        )

        tar_archive_file = tmp_path / "archive.tar"
        file_uri = URI.parse(f'file:///{str(tar_archive_file)}')

        archive.backup_io(IOThrottler.sync_reader(io.BytesIO(b'')), file_uri)  # just check that there is no error

    def test_extra_meta(self, tmp_path: pathlib.Path) -> None:
        test_data = io.BytesIO(b'Test data')
        archive = BackupArchiveV1()

        tar_archive_file = tmp_path / "archive.tar"
        file_uri = URI.parse(f'file:///{str(tar_archive_file)}')
        archive.backup_io(IOThrottler.sync_reader(test_data), file_uri)

        header = BackupArchiveV1.extract_header_meta(file_uri)
        assert(header.extra is None)

        extra_data = {"data": [1, 2, 3]}
        archive = BackupArchiveV1(extra_meta=extra_data)
        archive.backup_io(IOThrottler.sync_reader(test_data), file_uri)

        header = BackupArchiveV1.extract_header_meta(file_uri)
        assert(header.extra == extra_data)

    @pytest.mark.parametrize(
        'compression_mode, backup_file, reference_size',
        [
            [CompressionMode.no_compression, 'backup', 9],
            [CompressionMode.gzip, 'backup.gz', 35],
            [CompressionMode.lzma, 'backup.xz', 68],
            [CompressionMode.bzip2, 'backup.bz2', 49]
        ]
    )
    def test_compression(
        self,
        compression_mode: CompressionMode,
        backup_file: str,
        reference_size: int,
        tmp_path: pathlib.Path
    ) -> None:
        test_data = io.BytesIO(b'Test data')
        archive = BackupArchiveV1(compression=compression_mode)

        tar_archive_file = tmp_path / "archive.tar"
        file_uri = URI.parse(f'file:///{str(tar_archive_file)}')
        archive.backup_io(IOThrottler.sync_reader(test_data), file_uri)

        assert(test_data.getvalue() == b''.join(BackupArchiveV1.extract_data(file_uri)))

        with tar_archive_file.open('rb') as f:
            assert(len(FileObjectTarReader(f).entry(backup_file).read()) == reference_size)

    @pytest.mark.parametrize('i', list(range(10)))  # some time this test fails
    def test_encryption(self, i: int, tmp_path: pathlib.Path) -> None:
        test_data = io.BytesIO(b'Test data')
        encryption_key = 'foobarfoobarfoobarfoobar'

        archive = BackupArchiveV1(encryption_key=encryption_key)

        tar_archive_file = tmp_path / "archive.tar"
        file_uri = URI.parse(f'file:///{str(tar_archive_file)}')
        archive.backup_io(IOThrottler.sync_reader(test_data), file_uri)

        assert(test_data.getvalue() == b''.join(BackupArchiveV1.extract_data(file_uri, encryption_key=encryption_key)))

        with pytest.raises(ValueError):
            # no password submitted
            cg(BackupArchiveV1.extract_data(file_uri))

        data = None
        with contextlib.suppress(RuntimeError):  # may PKCS7 error happen
            data = b''.join(BackupArchiveV1.extract_data(file_uri, encryption_key=(encryption_key + '-baaad')))

        assert(data != test_data.getvalue())

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
    def test_digest(
        self,
        hash_algos: typing.List[HashMethod],
        digests: typing.List[bytes],
        tmp_path: pathlib.Path
    ) -> None:
        test_data = io.BytesIO(b'Test data')
        archive = BackupArchiveV1(hash_algorithms=hash_algos)

        tar_archive_file = tmp_path / "archive.tar"
        file_uri = URI.parse(f'file:///{str(tar_archive_file)}')
        archive.backup_io(IOThrottler.sync_reader(test_data), file_uri)

        tail_meta = BackupArchiveV1.extract_tail_meta(file_uri)
        assert({x.algorithm for x in tail_meta.hashes} == set(hash_algos))

        for i, ha in enumerate(hash_algos):
            assert([x.digest for x in tail_meta.hashes if x.algorithm == ha] == [digests[i]])

    def test_hashes_validate_chain(self, tmp_path: pathlib.Path) -> None:
        test_data = io.BytesIO(b'Test data')
        archive = BackupArchiveV1(
            hash_algorithms=[HashMethod.md5, HashMethod.sha256]
        )

        tar_archive_file = tmp_path / "archive.tar"
        file_uri = URI.parse(f'file:///{str(tar_archive_file)}')

        archive.backup_io(IOThrottler.sync_reader(test_data), file_uri)

        header_meta = BackupArchiveV1.extract_header_meta(file_uri)
        tail_meta = BackupArchiveV1.extract_tail_meta(file_uri)

        tar_corrupted_archive_file = tmp_path / "corrupted-archive.tar"
        corrupted_file_uri = URI.parse(f'file:///{str(tar_corrupted_archive_file)}')

        with tar_archive_file.open('rb') as original_f:
            with tar_corrupted_archive_file.open('wb') as corrupted_f:
                header_file = TarDynamicEntry(
                    [header_meta.model_dump_json().encode()],
                    ArchiveInnerFiles.header_meta.value
                )

                archive_name = ArchiveInnerFiles.backup_file(header_meta)
                archive_file = TarDynamicEntry(
                    [FileObjectTarReader(original_f).entry(archive_name).read()],
                    archive_name
                )

                tail_meta.hashes[0].digest = (b'\x00' * len(tail_meta.hashes[0].digest))
                tail_file = TarDynamicEntry(
                    [tail_meta.model_dump_json().encode()],
                    ArchiveInnerFiles.tail_meta.value
                )

                IOTarArchiveWriter(corrupted_f).archive([tail_file, archive_file, header_file])

        with pytest.raises(ValueError):
            # corrupted hash
            BackupArchiveV1.validate_archive(corrupted_file_uri)

    def test_hashes_validate_chain_error(self, tmp_path: pathlib.Path) -> None:
        test_data = io.BytesIO(b'Test data')
        archive = BackupArchiveV1()

        tar_archive_file = tmp_path / "archive.tar"
        file_uri = URI.parse(f'file:///{str(tar_archive_file)}')

        archive.backup_io(IOThrottler.sync_reader(test_data), file_uri)

        with pytest.raises(ValueError):
            # no digests
            BackupArchiveV1.validate_archive(file_uri)

    def test_files(self, monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path) -> None:
        test_data = b'Test data'
        archive = BackupArchiveV1()

        tar_archive_file = tmp_path / "archive.tar"
        file_uri = URI.parse(f'file:///{str(tar_archive_file)}')

        with (tmp_path / "sample1").open('wb') as f:
            f.write(test_data + b'-sample1')

        with (tmp_path / "sample2").open('wb') as f:
            f.write(test_data + b'-sample2')

        old_cwd = os.getcwd()
        monkeypatch.chdir(str(tmp_path))
        archive.backup_files(['sample1', 'sample2'], file_uri)
        monkeypatch.chdir(old_cwd)

        destination_tar = tmp_path / "destination.tar"
        with destination_tar.open('wb') as df:
            cg(IOThrottler.sync_writer(BackupArchiveV1.extract_data(file_uri), df))

        dest_file_uri = URI.parse(f'file:///{str(destination_tar)}')
        with IOVirtualClient.create_n_open(dest_file_uri) as c:
            tar_reader = ClientTarArchiveReader(c.client(), c.filename())
            assert(tar_reader.entry('sample1').read() == test_data + b'-sample1')
            assert(tar_reader.entry('sample2').read() == test_data + b'-sample2')

    def test_corrupted_link(self, monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path) -> None:
        monkeypatch.chdir(str(tmp_path))
        os.symlink('invalid-file.txt', 'link.txt')

        archive = BackupArchiveV1()

        tar_archive_file = tmp_path / "archive.tar"
        file_uri = URI.parse(f'file:///{str(tar_archive_file)}')
        archive.backup_files(['link.txt'], file_uri)

    def test_directory(self, monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path) -> None:
        monkeypatch.chdir(str(tmp_path))
        os.mkdir('empty-dir')

        archive = BackupArchiveV1()

        tar_archive_file = tmp_path / "archive.tar"
        file_uri = URI.parse(f'file:///{str(tar_archive_file)}')
        archive.backup_files(['empty-dir'], file_uri)
