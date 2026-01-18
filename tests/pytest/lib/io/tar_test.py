# -*- coding: utf-8 -*-

import asyncio
import pathlib
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
                    TarInnerGenerator(
                        [test_data],  # type: ignore[arg-type]
                        len(test_data),
                        str((tmp_path / "sample2").relative_to('/'))
                    )
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

            assert((tmp_path / (tmp_path / 'sample1').relative_to('/')).open('rb').read() == test_data)
            assert((tmp_path / (tmp_path / 'sample2').relative_to('/')).open('rb').read() == test_data)

    def test_exceptions(self, tmp_path: pathlib.Path) -> None:
        test_data = b'Test data'
        pyknic_tar_file = tmp_path / "pyknic-archive.tar"

        with pytest.raises(ValueError):
            _ = TarInnerGenerator([test_data], len(test_data), "/sample2")  # type: ignore[arg-type]

        with pytest.raises(ValueError):
            _ = TarInnerDynamicGenerator([test_data], "/sample2")  # type: ignore[arg-type]

        with pyknic_tar_file.open('wb') as f:
            tar_arch = TarArchive()

            def incorrect_size_file_gen(file_size: int) -> IOGenerator:
                with pytest.raises(ValueError):
                    yield from TarInnerGenerator(
                        [test_data], file_size, "sample2"  # type: ignore[arg-type]
                    ).entry()

            cg(IOThrottler.sync_writer(tar_arch._write(incorrect_size_file_gen(len(test_data) + 1)), f))
            cg(IOThrottler.sync_writer(tar_arch._write(incorrect_size_file_gen(len(test_data) - 1)), f))

    @pyknic_async_test
    async def test_dynamic(self, module_event_loop: asyncio.AbstractEventLoop, tmp_path: pathlib.Path) -> None:
        test_data = b'Test data'

        pyknic_tar_file = tmp_path / "pyknic-archive.tar"

        with (tmp_path / "sample1").open('wb') as f:
            f.write(test_data)

        with pyknic_tar_file.open('wb') as f:
            tar_arch = TarArchive()

            await tar_arch.dynamic_archive(
                f,  # type: ignore[arg-type]
                [
                    TarInnerFileGenerator(str(tmp_path / "sample1")),
                    TarInnerDynamicGenerator(
                        [test_data],  # type: ignore[arg-type]
                        str((tmp_path / "sample2").relative_to('/'))
                    )
                ]
            )

    def test_extract(self, tmp_path: pathlib.Path) -> None:
        test_data = b'Test data'

        pyknic_tar_file = tmp_path / "pyknic-archive.tar"

        with pyknic_tar_file.open('wb') as f:
            tar_arch = TarArchive()

            cg(IOThrottler.sync_writer(
                tar_arch.static_archive([
                    TarInnerGenerator(
                        [test_data],  # type: ignore[arg-type]
                        len(test_data),
                        str((tmp_path / "sample").relative_to('/'))
                    )
                ]),
                f
            ))

        with pyknic_tar_file.open('rb') as f:
            tar_arch = TarArchive()
            result = b''.join(
                tar_arch.extract(f, str((tmp_path / "sample").relative_to('/')))  # type: ignore[arg-type]
            )

            assert(result == test_data)
