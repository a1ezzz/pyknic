# -*- coding: utf-8 -*-

import pathlib
import tarfile
import typing

import pytest

from pyknic.lib.io import IOGenerator
from pyknic.lib.io.aio_wrapper import IOThrottler
from pyknic.lib.io.clients import IOVirtualClient, IOClientProto
from pyknic.lib.io.tar.readers import TarArchiveReaderProto, IOTarArchiveReader, ClientTarArchiveReader, TarReaderEntry
from pyknic.lib.io.tar.readers import FileObjectTarReader
from pyknic.lib.uri import URI


def test_abstract() -> None:
    pytest.raises(TypeError, TarArchiveReaderProto)
    pytest.raises(NotImplementedError, TarArchiveReaderProto.inner_entries, None)
    pytest.raises(NotImplementedError, TarArchiveReaderProto.entry, None, '')


class TestTarArchiveReader:

    @staticmethod
    def io_reader(file_path: str) -> IOTarArchiveReader:
        f = open(file_path, 'rb')  # no problem to keep file opened for tests
        return IOTarArchiveReader(IOThrottler.sync_reader(f))

    @staticmethod
    def client_reader(file_path: str) -> ClientTarArchiveReader:
        uri = URI.parse(f'file:///{file_path}')
        file_name, modified_uri = uri.get_file()
        client = IOVirtualClient.create_client(modified_uri)

        return ClientTarArchiveReader(client, file_name)

    @staticmethod
    def fo_reader(file_path: str) -> FileObjectTarReader:
        f = open(file_path, 'rb')  # no problem to keep file opened for tests
        return FileObjectTarReader(f)

    @pytest.mark.parametrize(
        "reader_impl", [
            io_reader,
            client_reader,
            fo_reader
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
        self, reader_impl: typing.Callable[[str], TarArchiveReaderProto], test_data: bytes, tmp_path: pathlib.Path
    ) -> None:
        pyknic_tar_file = tmp_path / "pyknic-archive.tar"

        with (tmp_path / "sample1").open('wb') as f:
            f.write(test_data)

        with (tmp_path / "sample2").open('wb') as f:
            f.write(test_data)

        with (tmp_path / "sample3").open('wb') as f:
            f.write(test_data)

        with tarfile.open(pyknic_tar_file, 'w') as tar:
            tar.add(str(tmp_path / "sample1"))
            tar.add(str(tmp_path / "sample2"))
            tar.add(str(tmp_path / "sample3"))

        # for inner_entries  (without conditions) tests
        reader = reader_impl(str(pyknic_tar_file))

        unarchive_gen = reader.inner_entries()
        next_entry = next(unarchive_gen)
        assert(isinstance(next_entry, TarReaderEntry))
        assert(next_entry.tar_info().name == str((tmp_path / "sample1").relative_to('/')))
        assert(next_entry.is_wasted() is False)
        data = b''
        for i in next_entry.data():
            data += i
        assert(next_entry.is_wasted() is True)
        assert(data == test_data)

        next_entry = next(unarchive_gen)
        assert(next_entry.tar_info().name == str((tmp_path / "sample2").relative_to('/')))

        with pytest.raises(RuntimeError):
            # entry should be read first
            next(unarchive_gen)

        # for inner_entries  (with conditions) tests
        reader = reader_impl(str(pyknic_tar_file))

        unarchive_gen = reader.inner_entries(
            str((tmp_path / "sample1").relative_to('/')),
            str((tmp_path / "sample3").relative_to('/'))
        )

        next_entry = next(unarchive_gen)
        assert(next_entry.tar_info().name == str((tmp_path / "sample1").relative_to('/')))
        next_entry.flush()

        next_entry = next(unarchive_gen)
        assert(next_entry.tar_info().name == str((tmp_path / "sample3").relative_to('/')))
        next_entry.flush()

        with pytest.raises(StopIteration):
            _ = next(unarchive_gen)

        # for entry test
        reader = reader_impl(str(pyknic_tar_file))
        sample1_entry = reader.entry(str((tmp_path / "sample1").relative_to('/')))
        assert(sample1_entry.read() == test_data)

        # for exception test
        reader = reader_impl(str(pyknic_tar_file))
        with pytest.raises(FileNotFoundError):
            reader.entry('unknown-sample')


class TestIOTarArchiveReader:

    def test_exceptions(self) -> None:
        empty_reader = IOTarArchiveReader([b''])
        list(empty_reader.inner_entries())

        with pytest.raises(ValueError):
            list(empty_reader.inner_entries())


class TestClientTarArchiveReader:

    def test_exceptions(self) -> None:
        class UselessClient(IOClientProto):

            def uri(self) -> URI:
                raise ValueError('!')

            @classmethod
            def create_client(cls, uri: URI) -> 'IOClientProto':
                return cls()

        class RClient(IOClientProto):

            def uri(self) -> URI:
                raise ValueError('!')

            @classmethod
            def create_client(cls, uri: URI) -> 'IOClientProto':
                return cls()

            def receive_file(self, remote_file_name: str) -> IOGenerator:
                yield b''

        incorrect_client = UselessClient()
        receive_client = RClient()

        with pytest.raises(ValueError):
            ClientTarArchiveReader(incorrect_client, 'archive')

        with pytest.raises(ValueError):
            ClientTarArchiveReader(receive_client, 'archive')
