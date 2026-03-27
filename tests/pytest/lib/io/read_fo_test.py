# -*- coding: utf-8 -*-

import pathlib
import pytest
import shutil

from pyknic.lib.io.read_fo import ReadFileObject


class TestReadFileObject:

    def test(self, tmp_path: pathlib.Path) -> None:
        test_data = b'Info!'
        test_file = tmp_path / "test_file"

        test_fo = ReadFileObject([test_data])

        with test_file.open('wb') as write_file:
            shutil.copyfileobj(test_fo, write_file)

        with test_file.open('rb') as read_file:
            assert(read_file.read() == test_data)

    def test_base_methods(self) -> None:
        test_fo = ReadFileObject([b'!'])
        assert(test_fo.readable() is True)
        assert(test_fo.seekable() is False)
        assert(test_fo.writable() is False)
        assert(test_fo.isatty() is False)

        with pytest.raises(OSError):
            _ = test_fo.fileno()

    def test_read_closed_obj(self) -> None:
        test_fo = ReadFileObject([b'!'])
        assert(test_fo.read() == b'!')

        test_fo = ReadFileObject([b'!'])
        test_fo.close()
        with pytest.raises(ValueError):
            _ = test_fo.read()

    def test_prefetch(self) -> None:
        test_fo = ReadFileObject([b'some-long-data'])
        assert(test_fo.read(0) == b'')
        assert(test_fo.read(1) == b's')
        assert(test_fo.read(0) == b'')
        assert(test_fo.read(3) == b'ome')
        assert(test_fo.read() == b'-long-data')
