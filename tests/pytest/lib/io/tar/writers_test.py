# -*- coding: utf-8 -*-

import pathlib
import tarfile
import typing

import pytest

from pyknic.lib.io.aio_wrapper import IOThrottler, cg
from pyknic.lib.io.clients import IOVirtualClient
from pyknic.lib.io.tar.writers import TarWriterEntryProto, _TarInfoGenerator, TarFileEntry, TarDynamicEntry
from pyknic.lib.io.tar.writers import TarArchiveWriterProto, IOTarArchiveWriter, ClientTarArchiveWriter
from pyknic.lib.io.tar.writers import TarFileGenerator
from pyknic.lib.uri import URI


def test_abstract() -> None:
    pytest.raises(TypeError, TarWriterEntryProto)
    pytest.raises(NotImplementedError, TarWriterEntryProto.tar_info, None)
    pytest.raises(NotImplementedError, TarWriterEntryProto.data, None)

    pytest.raises(TypeError, TarArchiveWriterProto)
    pytest.raises(NotImplementedError, TarArchiveWriterProto.archive, None, None)


class Test_TarInfoGenerator:

    def test(self) -> None:

        with pytest.raises(ValueError):
            # absolute path is not allowed
            _TarInfoGenerator.custom_tar_info('/sample')

        tar_info = _TarInfoGenerator.custom_tar_info('sample')

        with pytest.raises(ValueError):
            # expected_size is not aligned
            _TarInfoGenerator.tar_info_pax_padding(tar_info, expected_size=600)

        with pytest.raises(ValueError):
            tar_info.size = (9 * (1024 ** 3))
            # expected_size is smaller than an info
            _TarInfoGenerator.tar_info_pax_padding(tar_info, expected_size=512)


class TestTarArchiveWriter:

    @staticmethod
    def io_writer(file_path: str, sources: typing.Iterable[TarWriterEntryProto]) -> None:
        with open(file_path, 'wb') as f:
            writer = IOTarArchiveWriter(f)
            writer.archive(sources)

    @staticmethod
    def client_writer(file_path: str, sources: typing.Iterable[TarWriterEntryProto]) -> None:
        uri = URI.parse(f'file:///{file_path}')
        file_name, modified_uri = uri.get_file()

        client = IOVirtualClient.create_client(modified_uri)
        with client.open():
            writer = ClientTarArchiveWriter(client, file_name)
            writer.archive(sources)

    @pytest.mark.parametrize(
        "writer_impl", [
            io_writer,
            client_writer,
        ]
    )
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
    def test(
        self,
        writer_impl: typing.Callable[[str, typing.Iterable[TarWriterEntryProto]], None],
        test_data: bytes,
        tmp_path: pathlib.Path
    ) -> None:
        pyknic_tar_file = tmp_path / "pyknic-archive.tar"

        with (tmp_path / "sample1").open('wb') as f:
            f.write(test_data)

        writer_impl(
            str(pyknic_tar_file),
            [
                TarFileEntry(str(tmp_path / "sample1")),
                TarDynamicEntry([test_data], str((tmp_path / "sample2").relative_to('/')))
            ]
        )

        inner_files = [
            str((tmp_path / 'sample1').relative_to('/')),
            str((tmp_path / 'sample2').relative_to('/'))
        ]

        self.__check_archive(pyknic_tar_file, inner_files, test_data)

    def __check_archive(
        self, archive: pathlib.Path, expected_files: typing.Iterable[str], test_data: bytes
    ) -> None:

        with tarfile.open(archive) as tar:
            inner_names = list(tar.getnames())
            inner_names.sort()

            expected_files_list = list(expected_files)
            expected_files_list.sort()

            assert(inner_names == expected_files_list)

            for i in expected_files_list:
                info = tar.getmember(i)
                assert(info.size == len(test_data))

                tar_fo = tar.extractfile(info)
                assert(tar_fo)
                assert(tar_fo.read() == test_data)

    def test_generator(self, tmp_path: pathlib.Path) -> None:
        pyknic_tar_file = tmp_path / "pyknic-archive.tar"

        test_data = b'Test data'

        with (tmp_path / "sample1").open('wb') as f:
            f.write(test_data)

        with (tmp_path / "sample2").open('wb') as f:
            f.write(test_data)

        with pyknic_tar_file.open('wb') as tar:
            cg(IOThrottler.sync_writer(
                TarFileGenerator.tar([
                    str(tmp_path / "sample1"),
                    str(tmp_path / "sample2"),
                ]),
                tar
            ))

        inner_files = [
            str((tmp_path / 'sample1').relative_to('/')),
            str((tmp_path / 'sample2').relative_to('/'))
        ]

        self.__check_archive(pyknic_tar_file, inner_files, test_data)
