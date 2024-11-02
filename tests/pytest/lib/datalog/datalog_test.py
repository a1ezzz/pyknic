# -*- coding: utf-8 -*-

import functools
import threading
import typing
import pytest

from pyknic.lib.datalog.proto import DatalogProto
from pyknic.lib.datalog.datalog_py import DatalogPy
from pyknic.lib.datalog.datalog import Datalog


class TestDatalog:

    @pytest.mark.parametrize(
        "test_cls", [
            DatalogPy,
            Datalog
        ]
    )
    def test_plain(self, test_cls: typing.Type[DatalogProto]) -> None:
        test_obj = test_cls()
        assert(isinstance(test_obj, DatalogProto) is True)

        seq = [1, True, "foo", ("bar", 0)]
        for i in seq:
            test_obj.append(i)

        assert(list(test_obj.iterate()) == seq)

        test_obj.truncate(3)
        assert(list(test_obj.iterate()) == seq[-3:])

        test_obj.truncate(0)
        assert(list(test_obj.iterate()) == list())

    @pytest.mark.parametrize(
        "test_cls", [
            DatalogPy,
            Datalog
        ]
    )
    def test_concurrency(self, test_cls: typing.Type[DatalogProto]) -> None:
        test_obj = test_cls()
        start_event = threading.Event()

        def concurrency_push(number_of_object: int) -> None:
            nonlocal test_obj, start_event
            start_event.wait()
            for i in range(number_of_object):
                test_obj.append(i)

        threads_number = 20
        number_of_objects = 1000
        threads = [
            threading.Thread(target=functools.partial(concurrency_push, number_of_objects))
            for _ in range(threads_number)
        ]

        for th in threads:
            th.start()

        start_event.set()
        for th in threads:
            th.join()

        result = list(test_obj.iterate())
        result.sort()

        expected_result = ([x for x in range(number_of_objects)] * threads_number)
        expected_result.sort()

        assert(result == expected_result)
