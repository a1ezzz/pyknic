# -*- coding: utf-8 -*-

import asyncio
import io
import os
import pathlib
import sys
import tarfile
import typing

import pytest

from pyknic.lib.io import IOGenerator
from pyknic.lib.io.aio_wrapper import IOThrottler, cg
from pyknic.lib.io.tar import StaticTarEntryProto, DynamicTarEntryProto
from pyknic.lib.io.tar import TarInnerFileGenerator, TarInnerGenerator, TarArchive, TarInnerDynamicGenerator
from pyknic.lib.io.tar import TarArchiveReaderProto, IOTarReader, URITarReader
from pyknic.lib.uri import URI

from fixtures.asyncio import pyknic_async_test


S3ConnectionEnvVar = "S3_TEST_URI"


def test_abstract() -> None:
    pytest.raises(TypeError, StaticTarEntryProto)
    pytest.raises(NotImplementedError, StaticTarEntryProto.entry, None)

    pytest.raises(TypeError, DynamicTarEntryProto)
    pytest.raises(NotImplementedError, DynamicTarEntryProto.entry, None, None)

    pytest.raises(TypeError, TarArchiveReaderProto)
    pytest.raises(NotImplementedError, TarArchiveReaderProto.entries, None)
    pytest.raises(NotImplementedError, TarArchiveReaderProto.inner_descriptors, None)


class TestTarArchive:

    @pytest.mark.parametrize(
        "test_data",
        [
            b'Test data',
            b'',
            b'1' * tarfile.BLOCKSIZE,
            b'3' * tarfile.RECORDSIZE,
        ],
        ids=[
            "small-data",
            "null-data",
            "blocksize-aligned-data",
            "record-aligned-data"
        ]
    )
    def test(self, test_data: bytes, tmp_path: pathlib.Path) -> None:
        pyknic_tar_file = tmp_path / "pyknic-archive.tar"

        with (tmp_path / "sample1").open('wb') as f:
            f.write(test_data)

        with pyknic_tar_file.open('wb') as f:
            tar_arch = TarArchive()

            cg(IOThrottler.sync_writer(
                tar_arch.static_archive([
                    TarInnerFileGenerator(str(tmp_path / "sample1")),
                    TarInnerGenerator([test_data], len(test_data), str((tmp_path / "sample2").relative_to('/')))
                ]),
                f
            ))

        with tarfile.open(pyknic_tar_file) as tar:
            inner_names = list(tar.getnames())
            inner_names.sort()

            sample1_file = (tmp_path / 'sample1').relative_to('/')
            sample2_file = (tmp_path / 'sample2').relative_to('/')

            assert(inner_names == [str(sample1_file), str(sample2_file)])

            sample1_info = tar.getmember(str(sample1_file))
            assert(sample1_info.size == len(test_data))
            sample2_info = tar.getmember(str(sample2_file))
            assert(sample2_info.size == len(test_data))

            # TODO: enable filter by default when python 3.11 support ends
            if sys.version_info >= (3, 12, 0):

                tar.extract(sample1_info, tmp_path, filter='data')
                tar.extract(sample2_info, tmp_path, filter='data')
            else:
                tar.extract(sample1_info, tmp_path)
                tar.extract(sample2_info, tmp_path)

            assert((tmp_path / sample1_file).open('rb').read() == test_data)
            assert((tmp_path / sample2_file).open('rb').read() == test_data)

    @pytest.mark.parametrize(
        "test_data",
        [
            b'Test data',
            b'',
            b'1' * tarfile.BLOCKSIZE,
            b'3' * tarfile.RECORDSIZE,
        ],
        ids=[
            "small-data",
            "null-data",
            "blocksize-aligned-data",
            "record-aligned-data"
        ]
    )
    def test_exceptions(self, test_data: bytes, tmp_path: pathlib.Path) -> None:
        pyknic_tar_file = tmp_path / "pyknic-archive.tar"

        with pytest.raises(ValueError):
            # absolute path is not allowed
            _ = TarInnerGenerator([test_data], len(test_data), "/sample2")

        with pytest.raises(ValueError):
            # absolute path is not allowed
            _ = TarInnerDynamicGenerator([test_data], "/sample2")

        with pyknic_tar_file.open('wb') as f:
            tar_arch = TarArchive()

            def incorrect_size_file_gen(file_size: int) -> IOGenerator:
                with pytest.raises(ValueError):
                    yield from TarInnerGenerator([test_data], file_size, "sample2").entry()

            cg(IOThrottler.sync_writer(tar_arch._write(incorrect_size_file_gen(len(test_data) + 1)), f))
            cg(IOThrottler.sync_writer(tar_arch._write(incorrect_size_file_gen(len(test_data) - 1)), f))

    @pytest.mark.parametrize(
        "test_data",
        [
            b'Test data',
            b'',
            b'1' * tarfile.BLOCKSIZE,
            b'3' * tarfile.RECORDSIZE,
        ],
        ids=[
            "small-data",
            "null-data",
            "blocksize-aligned-data",
            "record-aligned-data"
        ]
    )
    def test_entries_exceptions(self, test_data: bytes, tmp_path: pathlib.Path) -> None:
        tar_arch = TarArchive()
        arch_gen = tar_arch.static_archive([
            TarInnerGenerator(
                [test_data], len(test_data), "sample1"
            ),
            TarInnerGenerator(
                [test_data], len(test_data), "sample2"
            )
        ])

        entries_gen = IOTarReader(arch_gen).entries()

        _ = next(entries_gen)
        with pytest.raises(RuntimeError):
            # data was not read from previous entry
            _ = next(entries_gen)

    @pyknic_async_test
    @pytest.mark.parametrize(
        "test_data",
        [
            b'Test data',
            b'',
            b'1' * tarfile.BLOCKSIZE,
            b'3' * tarfile.RECORDSIZE,
        ],
        ids=[
            "small-data",
            "null-data",
            "blocksize-aligned-data",
            "record-aligned-data"
        ]
    )
    async def test_dynamic_to_file(
        self, test_data: bytes, module_event_loop: asyncio.AbstractEventLoop, tmp_path: pathlib.Path
    ) -> None:
        pyknic_tar_file = tmp_path / "pyknic-archive.tar"

        with (tmp_path / "sample1").open('wb') as f:
            f.write(test_data)

        with pyknic_tar_file.open('wb') as f:
            tar_arch = TarArchive()

            await tar_arch.dynamic_archive_to_file(
                f,
                [
                    TarInnerFileGenerator(str(tmp_path / "sample1")),
                    TarInnerDynamicGenerator([test_data], str((tmp_path / "sample2").relative_to('/')))
                ]
            )

        with pyknic_tar_file.open('rb') as f:
            result = b''.join(
                TarArchive.extract_from_file(f, str((tmp_path / "sample1").relative_to('/')))
            )
            assert(result == test_data)

            result = b''.join(
                TarArchive.extract_from_file(f, str((tmp_path / "sample2").relative_to('/')))
            )
            assert(result == test_data)

    @pyknic_async_test
    @pytest.mark.parametrize(
        "test_data",
        [
            b'Test data',
            b'',
            b'1' * tarfile.BLOCKSIZE,
            b'3' * tarfile.RECORDSIZE,
        ],
        ids=[
            "small-data",
            "null-data",
            "blocksize-aligned-data",
            "record-aligned-data"
        ]
    )
    async def test_dynamic_to_uri(
        self, test_data: bytes, module_event_loop: asyncio.AbstractEventLoop, tmp_path: pathlib.Path
    ) -> None:

        with (tmp_path / "sample1").open('wb') as f:
            f.write(test_data)

        uri = URI.parse(f'file:///{tmp_path}/pyknic-archive.tar')
        tar_arch = TarArchive()
        await tar_arch.dynamic_archive_to_uri(
            uri,
            [
                TarInnerFileGenerator(str(tmp_path / "sample1")),
                TarInnerDynamicGenerator([test_data], str((tmp_path / "sample2").relative_to('/')))
            ]
        )

        with (tmp_path / 'pyknic-archive.tar').open('rb') as f:
            result = b''.join(
                TarArchive.extract_from_file(f, str((tmp_path / "sample1").relative_to('/')))
            )
            assert(result == test_data)

            result = b''.join(
                TarArchive.extract_from_file(f, str((tmp_path / "sample2").relative_to('/')))
            )
            assert(result == test_data)

    @pytest.mark.parametrize(
        "test_data",
        [
            b'Test data',
            b'',
            b'1' * tarfile.BLOCKSIZE,
            b'3' * tarfile.RECORDSIZE,
        ],
        ids=[
            "small-data",
            "null-data",
            "blocksize-aligned-data",
            "record-aligned-data"
        ]
    )
    def test_extract(self, test_data: bytes, tmp_path: pathlib.Path) -> None:
        pyknic_tar_file = tmp_path / "pyknic-archive.tar"

        with pyknic_tar_file.open('wb') as f:
            tar_arch = TarArchive()

            cg(IOThrottler.sync_writer(
                tar_arch.static_archive([
                    TarInnerGenerator([test_data], len(test_data), str((tmp_path / "sample").relative_to('/')))
                ]),
                f
            ))

        with pyknic_tar_file.open('rb') as f:
            result = b''.join(
                TarArchive.extract_from_file(f, str((tmp_path / "sample").relative_to('/')))
            )

            assert(result == test_data)

    @pytest.mark.parametrize(
        "test_data",
        [
            b'Test data',
            b'',
            b'1' * tarfile.BLOCKSIZE,
            b'3' * tarfile.RECORDSIZE,
        ],
        ids=[
            "small-data",
            "null-data",
            "blocksize-aligned-data",
            "record-aligned-data"
        ]
    )
    def test_plain_entries(self, test_data: bytes, tmp_path: pathlib.Path) -> None:
        with (tmp_path / "sample1").open('wb') as f:
            f.write(test_data)

        inner_path = str((tmp_path / "sample").relative_to('/'))
        tar_arch = TarArchive()
        archive_gen = tar_arch.static_archive([
            TarInnerGenerator([test_data], len(test_data), inner_path)
        ])

        unarchive_gen = IOTarReader(archive_gen).entries()
        next_entry = next(unarchive_gen)
        assert(next_entry.tar_info().name == inner_path)
        assert(next_entry.is_wasted() is False)
        data = b''
        for i in next_entry.data():
            data += i
        assert(next_entry.is_wasted() is True)
        assert(data == test_data)

        with pytest.raises(StopIteration):
            next(unarchive_gen)

    @pytest.mark.parametrize(
        'tar_format, bad_format',
        [
            [tarfile.PAX_FORMAT, False],
            [tarfile.GNU_FORMAT, False],
            [tarfile.USTAR_FORMAT, True],
        ]
    )
    def test_non_classic_tar_entries(self, tar_format: int, bad_format: bool, tmp_path: pathlib.Path) -> None:
        # Original tar limits names to 100 chars, inner sizes to 8GB and supports shorter links
        destination = 'a' * 200
        link_name = 'b' * 200
        os.symlink(destination, str(tmp_path / link_name))

        pyknic_tar_file = tmp_path / "pyknic-archive.tar"

        def check_fn(fobj: typing.IO[bytes]) -> None:
            py_tar = tarfile.TarFile(fileobj=fobj, mode='w', format=tar_format)
            py_tar.add(str(tmp_path / link_name))

        if bad_format:
            with pyknic_tar_file.open('wb') as fw:
                with pytest.raises(ValueError):
                    check_fn(fw)
            return

        with pyknic_tar_file.open('wb') as fw:
            check_fn(fw)

        with pyknic_tar_file.open('rb') as fr:
            reader = IOThrottler.sync_reader(fr)
            entries = IOTarReader(reader).entries()
            next_entry = next(entries)

            assert(next_entry.tar_info().name == (str((tmp_path / link_name).relative_to('/'))))
            assert(next_entry.tar_info().linkname == destination)

    @pyknic_async_test
    async def test_huge_file(self, module_event_loop: asyncio.AbstractEventLoop) -> None:  # TODO: rename back
        # this test check possibility to archive files that are over 8GB

        class DummyIO(io.IOBase):

            def seek(self, offset, whence=..., /):  # type: ignore[no-untyped-def]  # just a stub
                return 0

            def truncate(self, size=..., /):  # type: ignore[no-untyped-def]  # just a stub
                return 0

            def write(self, data):  # type: ignore[no-untyped-def]  # just a stub
                return len(data)

            def seekable(self) -> bool:
                return True

        dummy_io = DummyIO()
        tar_arch = TarArchive()

        def data_generator() -> IOGenerator:
            for i in range(1024 * 9):
                yield b'\x00' * (1024 * 1024)  # megabyte

        await tar_arch.dynamic_archive_to_file(
            dummy_io,  # type: ignore[arg-type]
            [
                TarInnerDynamicGenerator(data_generator(), "sample2")
            ]
        )


class TestIOTarReader:

    @pytest.mark.parametrize(
        "test_data",
        [
            b'Test data',
            b'',
            b'1' * tarfile.BLOCKSIZE,
            b'3' * tarfile.RECORDSIZE,
        ],
        ids=[
            "small-data",
            "null-data",
            "blocksize-aligned-data",
            "record-aligned-data"
        ]
    )
    def test_entries(self, test_data: bytes, tmp_path: pathlib.Path) -> None:
        with (tmp_path / "sample1").open('wb') as f:
            f.write(test_data)

        with (tmp_path / "sample2").open('wb') as f:
            f.write(test_data)

        tar_arch = TarArchive()
        arch_gen = tar_arch.static_archive([
            TarInnerFileGenerator(str(tmp_path / "sample1")),
            TarInnerFileGenerator(str(tmp_path / "sample2")),
        ])

        entries_gen = IOTarReader(arch_gen).entries()

        next_entry = next(entries_gen)
        assert(next_entry.tar_info().name == str((tmp_path / "sample1").relative_to('/')))
        assert(next_entry.tar_info().size == len(test_data))
        assert(b''.join(next_entry.data()) == test_data)

        next_entry = next(entries_gen)
        assert(next_entry.tar_info().name == str((tmp_path / "sample2").relative_to('/')))
        assert(next_entry.tar_info().size == len(test_data))
        assert(b''.join(next_entry.data()) == test_data)

        with pytest.raises(StopIteration):
            next(entries_gen)

    @pytest.mark.parametrize(
        "test_data",
        [
            b'Test data',
            b'',
            b'1' * tarfile.BLOCKSIZE,
            b'3' * tarfile.RECORDSIZE,
        ],
        ids=[
            "small-data",
            "null-data",
            "blocksize-aligned-data",
            "record-aligned-data"
        ]
    )
    def test_inner_descriptors(self, test_data: bytes, tmp_path: pathlib.Path) -> None:
        with (tmp_path / "sample1").open('wb') as f:
            f.write(test_data)

        with (tmp_path / "sample2").open('wb') as f:
            f.write(test_data)

        tar_arch = TarArchive()
        arch_gen = tar_arch.static_archive([
            TarInnerFileGenerator(str(tmp_path / "sample1")),
            TarInnerFileGenerator(str(tmp_path / "sample2")),
        ])

        entries_gen = IOTarReader(arch_gen).inner_descriptors()

        next_entry = next(entries_gen)
        assert(next_entry.name == str((tmp_path / "sample1").relative_to('/')))

        next_entry = next(entries_gen)
        assert(next_entry.name == str((tmp_path / "sample2").relative_to('/')))

        with pytest.raises(StopIteration):
            next(entries_gen)


class TestURITarReader:

    def test_entries(self, tmp_path: pathlib.Path) -> None:
        test_data = b'Test data'

        with (tmp_path / "sample1").open('wb') as f:
            f.write(test_data)

        with (tmp_path / "sample2").open('wb') as f:
            f.write(test_data)

        tar_arch = TarArchive()
        arch_gen = tar_arch.static_archive([
            TarInnerFileGenerator(str(tmp_path / "sample1")),
            TarInnerFileGenerator(str(tmp_path / "sample2")),
        ])

        with (tmp_path / "archive.tar").open('wb') as f:
            cg(IOThrottler.sync_writer(arch_gen, f))

        uri = URI.parse(f'file:///{tmp_path}/archive.tar')

        entries_gen = URITarReader(uri).entries()

        next_entry = next(entries_gen)
        assert(next_entry.tar_info().name == str((tmp_path / "sample1").relative_to('/')))
        assert(next_entry.tar_info().size == len(test_data))
        assert(b''.join(next_entry.data()) == test_data)

        next_entry = next(entries_gen)
        assert(next_entry.tar_info().name == str((tmp_path / "sample2").relative_to('/')))
        assert(next_entry.tar_info().size == len(test_data))
        assert(b''.join(next_entry.data()) == test_data)

        with pytest.raises(StopIteration):
            next(entries_gen)

    def test_inner_descriptors(self, tmp_path: pathlib.Path) -> None:
        test_data = b'Test data'

        with (tmp_path / "sample1").open('wb') as f:
            f.write(test_data)

        with (tmp_path / "sample2").open('wb') as f:
            f.write(test_data)

        with (tmp_path / "sample3").open('wb') as f:
            f.write(test_data)

        tar_arch = TarArchive()
        arch_gen = tar_arch.static_archive([
            TarInnerFileGenerator(str(tmp_path / "sample1")),
            TarInnerFileGenerator(str(tmp_path / "sample2")),
            TarInnerFileGenerator(str(tmp_path / "sample3")),
        ])

        with (tmp_path / "archive.tar").open('wb') as f:
            cg(IOThrottler.sync_writer(arch_gen, f))

        uri = URI.parse(f'file:///{tmp_path}/archive.tar')

        entries_gen = URITarReader(uri).inner_descriptors()

        next_entry = next(entries_gen)
        assert(next_entry.name == str((tmp_path / "sample1").relative_to('/')))

        next_entry = next(entries_gen)
        assert(next_entry.name == str((tmp_path / "sample2").relative_to('/')))

        next_entry = next(entries_gen)
        assert(next_entry.name == str((tmp_path / "sample3").relative_to('/')))

        with pytest.raises(StopIteration):
            next(entries_gen)
