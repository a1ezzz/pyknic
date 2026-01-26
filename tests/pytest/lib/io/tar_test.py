# -*- coding: utf-8 -*-

import asyncio
import io
import os
import pathlib
import typing

import pytest
import sys
import tarfile

from pyknic.lib.io import IOGenerator
from pyknic.lib.io.aio_wrapper import IOThrottler, cg
from pyknic.lib.io.tar import StaticTarEntryProto, DynamicTarEntryProto
from pyknic.lib.io.tar import TarInnerFileGenerator, TarInnerGenerator, TarArchive, TarInnerDynamicGenerator

from fixtures.asyncio import pyknic_async_test


def test_abstract() -> None:
    pytest.raises(TypeError, StaticTarEntryProto)
    pytest.raises(NotImplementedError, StaticTarEntryProto.entry, None)

    pytest.raises(TypeError, DynamicTarEntryProto)
    pytest.raises(NotImplementedError, DynamicTarEntryProto.entry, None, None)


class TestTarArchive:

    def test(self, tmp_path: pathlib.Path) -> None:
        test_data = b'Test data'

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
            extract_kw = {}
            if sys.version_info[0] >= 3 and sys.version_info[1] >= 12:
                extract_kw['filter'] = 'data'

            tar.extract(sample1_info, tmp_path, **extract_kw)  # type: ignore[arg-type]  # test issue
            tar.extract(sample2_info, tmp_path, **extract_kw)  # type: ignore[arg-type]  # test issue

            assert((tmp_path / sample1_file).open('rb').read() == test_data)
            assert((tmp_path / sample2_file).open('rb').read() == test_data)

        with open(pyknic_tar_file, 'rb') as f:
            reader = IOThrottler.sync_reader(f)
            assert(
                [x.name for x in TarArchive().inner_descriptors(reader)] == [
                    str(sample1_file),
                    str(sample2_file)
                ]
            )

    def test_exceptions(self, tmp_path: pathlib.Path) -> None:
        test_data = b'Test data'
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

    def test_entries_exceptions(self, tmp_path: pathlib.Path) -> None:
        test_data = b'Test data'

        tar_arch = TarArchive()
        arch_gen = tar_arch.static_archive([
            TarInnerGenerator(
                [test_data], len(test_data), "sample1"
            ),
            TarInnerGenerator(
                [test_data], len(test_data), "sample2"
            )
        ])

        entries_gen = TarArchive.entries(arch_gen)

        _ = next(entries_gen)
        with pytest.raises(RuntimeError):
            # data was not read from previous entry
            _ = next(entries_gen)

    @pyknic_async_test
    async def test_dynamic(self, module_event_loop: asyncio.AbstractEventLoop, tmp_path: pathlib.Path) -> None:
        test_data = b'Test data'

        pyknic_tar_file = tmp_path / "pyknic-archive.tar"

        with (tmp_path / "sample1").open('wb') as f:
            f.write(test_data)

        with pyknic_tar_file.open('wb') as f:
            tar_arch = TarArchive()

            await tar_arch.dynamic_archive(
                f,
                [
                    TarInnerFileGenerator(str(tmp_path / "sample1")),
                    TarInnerDynamicGenerator([test_data], str((tmp_path / "sample2").relative_to('/')))
                ]
            )

    def test_extract(self, tmp_path: pathlib.Path) -> None:
        test_data = b'Test data'

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
            tar_arch = TarArchive()
            result = b''.join(
                tar_arch.extract(f, str((tmp_path / "sample").relative_to('/')))
            )

            assert(result == test_data)

    def test_plain_entries(self, tmp_path: pathlib.Path) -> None:
        test_data = b'Test data'

        with (tmp_path / "sample1").open('wb') as f:
            f.write(test_data)

        inner_path = str((tmp_path / "sample").relative_to('/'))
        tar_arch = TarArchive()
        archive_gen = tar_arch.static_archive([
            TarInnerGenerator([test_data], len(test_data), inner_path)
        ])

        unarchive_gen = TarArchive.entries(archive_gen)
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
            entries = TarArchive.entries(reader)
            next_entry = next(entries)

            assert(next_entry.tar_info().name == (str((tmp_path / link_name).relative_to('/'))))
            assert(next_entry.tar_info().linkname == destination)

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

        entries_gen = TarArchive.entries(arch_gen)

        next_entry = next(entries_gen)
        assert(next_entry.tar_info().name == str((tmp_path / "sample1").relative_to('/')))
        assert(b''.join(next_entry.data()) == test_data)

        next_entry = next(entries_gen)
        assert(next_entry.tar_info().name == str((tmp_path / "sample2").relative_to('/')))
        assert(b''.join(next_entry.data()) == test_data)

        with pytest.raises(StopIteration):
            next(entries_gen)

    def test_inner_descriptors(self, tmp_path: pathlib.Path) -> None:
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

        entries_gen = TarArchive.inner_descriptors(arch_gen)

        next_entry = next(entries_gen)
        assert(next_entry.name == str((tmp_path / "sample1").relative_to('/')))

        next_entry = next(entries_gen)
        assert(next_entry.name == str((tmp_path / "sample2").relative_to('/')))

        with pytest.raises(StopIteration):
            next(entries_gen)

    @pyknic_async_test
    async def test_huge_file(self, module_event_loop: asyncio.AbstractEventLoop) -> None:
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

        await tar_arch.dynamic_archive(
            dummy_io,  # type: ignore[arg-type]
            [
                TarInnerDynamicGenerator(data_generator(), "sample2")
            ]
        )
