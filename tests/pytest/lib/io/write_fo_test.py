# -*- coding: utf-8 -*-
import typing

from pyknic.lib.io.write_fo import WriteFileObject


class TestWriteFileObject:

    def test(self) -> None:

        def test_write_fn(f_obj: typing.BinaryIO) -> None:
            f_obj.write(b"hello")

        wfo = WriteFileObject(test_write_fn)
        assert(b''.join(wfo()) == b"hello")
