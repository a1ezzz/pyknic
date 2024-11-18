# -*- coding: utf-8 -*-

import functools
import threading
import typing
import pytest

from dataclasses import dataclass

if typing.TYPE_CHECKING:
    # noinspection PyUnresolvedReferences
    from conftest import SignalsRegistry

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
        reversed_seq = seq.copy()
        reversed_seq.reverse()

        for i in seq:
            test_obj.append(i)

        assert(list(test_obj.iterate()) == seq)
        assert(list(test_obj.iterate(reverse=True)) == reversed_seq)

        test_obj.truncate(3)
        result = seq[-3:]
        reversed_result = result.copy()
        reversed_result.reverse()
        assert(list(test_obj.iterate()) == result)
        assert(list(test_obj.iterate(reverse=True)) == reversed_result)

        test_obj.truncate(0)
        assert(list(test_obj.iterate()) == list())
        assert(list(test_obj.iterate(reverse=True)) == list())

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

    @pytest.mark.parametrize(
        "test_cls", [
            DatalogPy,
            Datalog
        ]
    )
    def test_truncate(self, test_cls: typing.Type[DatalogProto]) -> None:
        test_obj = test_cls()

        for i in range(10):
            test_obj.append(i)

        test_obj.truncate(7)
        assert(list(test_obj.iterate()) == [3, 4, 5, 6, 7, 8, 9])

    @pytest.mark.parametrize(
        "test_cls", [
            DatalogPy,
            Datalog
        ]
    )
    def test_signal(self, test_cls: typing.Type[DatalogProto], signals_registry: 'SignalsRegistry') -> None:
        pass

    @pytest.mark.parametrize(
        "test_cls", [
            DatalogPy,
            Datalog
        ]
    )
    def test_find(self, test_cls: typing.Type[DatalogProto]) -> None:

        @dataclass
        class LogEntry:
            str_field: str
            int_field: int
            optional_float_field: typing.Optional[float]

        test_obj = test_cls()
        first_record = LogEntry('foo', 10, None)
        second_record = LogEntry('bar', 5, None)
        third_record = LogEntry('other string', 5, 0.1)
        fourth_record = LogEntry('one more string', 12, None)

        test_obj.append(first_record)
        test_obj.append(second_record)
        test_obj.append(third_record)
        test_obj.append(fourth_record)

        assert(test_obj.find(lambda x: x.optional_float_field is None) is first_record)
        assert(test_obj.find(lambda x: x.optional_float_field is None, reverse=True) is fourth_record)

        assert(test_obj.find(lambda x: x.optional_float_field is not None) is third_record)
        assert(test_obj.find(lambda x: x.optional_float_field is not None, reverse=True) is third_record)

        assert(test_obj.find(lambda x: x.int_field == 5) is second_record)
        assert(test_obj.find(lambda x: x.int_field == 5, reverse=True) is third_record)

        assert(test_obj.find(lambda x: x.int_field == 13) is None)
        assert(test_obj.find(lambda x: x.int_field == 13, reverse=True) is None)
