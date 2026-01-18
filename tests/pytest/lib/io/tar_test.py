# -*- coding: utf-8 -*-

import pathlib
import pytest
import sys
import tarfile

from pyknic.lib.io import IOGenerator
from pyknic.lib.io.aio_wrapper import IOThrottler, cg
from pyknic.lib.io.tar import TarInnerFileGenerator, TarArchiveGenerator


class TestTarArchiveGenerator:

    def test(self, tmp_path: pathlib.Path) -> None:
        test_data = b'Test data'

        pyknic_tar_file = tmp_path / "pyknic-archive.tar"

        with (tmp_path / "sample1").open('wb') as f:
            f.write(test_data)

        with pyknic_tar_file.open('wb') as f:
            tar_arch = TarArchiveGenerator()

            def file_gen() -> IOGenerator:
                inner_file = TarInnerFileGenerator()

                yield from inner_file.file(str(tmp_path / "sample1"))
                yield from inner_file.generator(
                    [test_data], len(test_data), str((tmp_path / "sample2").relative_to('/'))
                )

            cg(IOThrottler.sync_writer(tar_arch.write(file_gen()), f))

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

        with pyknic_tar_file.open('wb') as f:
            tar_arch = TarArchiveGenerator()

            def incorrect_size_file_gen(file_size) -> IOGenerator:
                inner_file = TarInnerFileGenerator()

                with pytest.raises(ValueError):
                    yield from inner_file.generator([test_data], file_size, "sample2")

            def incorrect_filename_gen() -> IOGenerator:
                inner_file = TarInnerFileGenerator()

                with pytest.raises(ValueError):
                    yield from inner_file.generator([test_data], len(test_data), "/sample2")

            cg(IOThrottler.sync_writer(tar_arch.write(incorrect_size_file_gen(len(test_data) + 1)), f))
            cg(IOThrottler.sync_writer(tar_arch.write(incorrect_size_file_gen(len(test_data) - 1)), f))

            cg(IOThrottler.sync_writer(tar_arch.write(incorrect_filename_gen()), f))
