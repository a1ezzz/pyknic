# -*- coding: utf-8 -*-

import io
import pathlib
import pytest
import sys
import tarfile

from pyknic.lib.tar_archiver import TarArchiver


class TestTarArchiver:

    def test_append_io(self, tmp_path: pathlib.Path) -> None:
        test_data = b'Test data'
        test_io = io.BytesIO(test_data)
        archiver = TarArchiver()

        tar_archive_file = tmp_path / "archive.tar"

        with tar_archive_file.open('wb') as f:
            with archiver.create(f) as ar:  # type: ignore[arg-type]  # the 'wb' flags return correct type
                ar.append_io(test_io, 'sample1')
                ar.append_io(test_io, 'sample2')

        with tarfile.open(tar_archive_file) as tar:
            inner_names = list(tar.getnames())
            inner_names.sort()
            assert(inner_names == ['sample1', 'sample2'])

            sample1_info = tar.getmember('sample1')
            assert(sample1_info.size == len(test_data))

            sample2_info = tar.getmember('sample2')
            assert(sample2_info.size == len(test_data))

            # TODO: enable filter by default when python 3.11 support ends
            extract_kw = {}
            if sys.version_info[0] >= 3 and sys.version_info[1] >= 12:
                extract_kw['filter'] = 'data'

            tar.extract(sample1_info, tmp_path, **extract_kw)  # type: ignore[arg-type]  # test issue
            tar.extract(sample2_info, tmp_path, **extract_kw)  # type: ignore[arg-type]  # test issue
            assert((tmp_path / 'sample1').open('rb').read() == test_data)
            assert((tmp_path / 'sample2').open('rb').read() == test_data)

    def test_sizes(self, tmp_path: pathlib.Path) -> None:
        test_data = b'Test data'
        test_io = io.BytesIO(test_data)
        archiver = TarArchiver()

        pyknic_tar_file = tmp_path / "pyknic-archive.tar"

        with pyknic_tar_file.open('wb') as f:
            with archiver.create(f) as ar:  # type: ignore[arg-type]  # the 'wb' flags return correct type
                ar.append_io(test_io, 'sample1')
                ar.append_io(test_io, 'sample2')

        tar_tar_file = tmp_path / "tar-tar.tar"

        with (tmp_path / "sample1").open('wb') as f:
            f.write(test_data)

        with (tmp_path / "sample2").open('wb') as f:
            f.write(test_data)

        with tarfile.open(tar_tar_file, mode='w|') as tar:
            tar.add(tmp_path / "sample1")
            tar.add(tmp_path / "sample2")

        assert(pyknic_tar_file.stat().st_size == tar_tar_file.stat().st_size)

    def test_exception(self, tmp_path: pathlib.Path) -> None:
        test_io = io.BytesIO(b'Test data')
        archiver = TarArchiver()

        pyknic_tar_file = tmp_path / "archive.tar"

        with pytest.raises(ValueError):
            with pyknic_tar_file.open('wb') as f:
                with archiver.create(f) as ar:  # type: ignore[arg-type]  # the 'wb' flags return correct type
                    ar.append_io(test_io, 'sample1')
                    raise ValueError('!')

        assert(pyknic_tar_file.stat().st_size == 0)  # a file was truncated

    def test_append_file(self, tmp_path: pathlib.Path) -> None:
        test_data = b'Test data'
        archiver = TarArchiver()

        pyknic_tar_file = tmp_path / "pyknic-archive.tar"

        with (tmp_path / "sample1").open('wb') as f:
            f.write(test_data)

        with (tmp_path / "sample2").open('wb') as f:
            f.write(test_data)

        with pyknic_tar_file.open('wb') as f:
            with archiver.create(f) as ar:  # type: ignore[arg-type]  # the 'wb' flags return correct type
                ar.append_file(tmp_path / "sample1")
                ar.append_file(tmp_path / "sample2")

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
            assert((tmp_path / 'sample1').open('rb').read() == test_data)
            assert((tmp_path / 'sample2').open('rb').read() == test_data)
