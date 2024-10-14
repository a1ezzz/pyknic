# -*- coding: utf-8 -*-

import gc
import typing
import pytest

from pyknic.lib.signals.proto import Signal, SignalSourceProto, UnknownSignalException
from pyknic.lib.signals.source import SignalSourceMeta, SignalSource, BoundedCallback


class TestSignalSourceMeta:

    def test(self) -> None:

        class A(metaclass=SignalSourceMeta):
            pass

        assert(A.__pyknic_signals__ == set())  # type: ignore[attr-defined] # metaclass and mypy issues

        class B(metaclass=SignalSourceMeta):
            signal1 = Signal()
            signal2 = Signal()

        assert(B.__pyknic_signals__ == {B.signal1, B.signal2})  # type: ignore[attr-defined] # metaclass and mypy issues
        assert(B.signal1.__pyknic_signal_name__ == 'B.signal1')
        assert(B.signal2.__pyknic_signal_name__ == 'B.signal2')

        class C(B):
            signal3 = Signal()

        assert(C.signal1.__pyknic_signal_name__ == 'B.signal1')
        assert(C.signal2.__pyknic_signal_name__ == 'B.signal2')

        with pytest.raises(TypeError):
            class D(B):
                signal1 = Signal()  # signals may not be overridden


class TestSignalSource:

    def test(self) -> None:
        source = SignalSource()
        assert(isinstance(source, SignalSource) is True)
        assert(isinstance(source, SignalSourceProto) is True)

        pytest.raises(UnknownSignalException, source.emit, Signal())
        pytest.raises(UnknownSignalException, source.callback, Signal(), lambda: None)
        pytest.raises(UnknownSignalException, source.remove_callback, Signal(), lambda: None)

    def test_emit(self) -> None:
        class Source(SignalSource):
            signal1 = Signal()
            signal2 = Signal(int)

        results = []

        def callback(source: SignalSourceProto, signal: Signal, value: typing.Any) -> None:
            nonlocal results
            results.append((source, signal, value))

        s = Source()
        s.callback(Source.signal1, callback)
        assert(results == [])
        s.emit(Source.signal1)
        s.emit(Source.signal2, 1)
        assert(results == [(s, Source.signal1, None)])

        pytest.raises(TypeError, s.emit, Source.signal2, 'foo')

        results.clear()
        s.callback(Source.signal2, callback)
        s.emit(Source.signal1)
        s.emit(Source.signal2, 1)
        assert(results == [(s, Source.signal1, None), (s, Source.signal2, 1)])

        results.clear()
        s.remove_callback(Source.signal1, callback)
        s.emit(Source.signal1)
        s.emit(Source.signal2, 1)
        assert(results == [(s, Source.signal2, 1)])

    def test_bounded_callbacks(self) -> None:

        class Source(SignalSource):
            signal1 = Signal()

        class A:
            def callback(self, source: SignalSourceProto, signal: Signal, value: typing.Any) -> None:
                pass

            @classmethod
            def cls_callback(cls, source: SignalSourceProto, signal: Signal, value: typing.Any) -> None:
                pass

            def __call__(self, source: SignalSourceProto, signal: Signal, value: typing.Any) -> None:
                pass

        s = Source()
        with pytest.raises(ValueError):
            s.callback(Source.signal1, A().callback)

        s.callback(Source.signal1, A.cls_callback)  # classmethods are ok
        s.callback(Source.signal1, A())  # callable objects are ok too


class TestBoundedCallback:

    def test(self) -> None:
        results = []

        class Source(SignalSource):
            signal1 = Signal()

        class A:

            def callback(self, source: SignalSourceProto, signal: Signal, value: typing.Any) -> None:
                nonlocal results
                results.append((source, signal, value))

        s = Source()

        b = BoundedCallback(A().callback)
        s.callback(Source.signal1, b)  # this is ok, but callback will not be executed
        # since 'A()' will be collected
        gc.collect()
        s.emit(Source.signal1)
        assert (results == [])

        a = A()
        b = BoundedCallback(a.callback)
        s.callback(Source.signal1, b)  # this is ok totally
        gc.collect()
        s.emit(Source.signal1)
        assert (results == [(s, Source.signal1, None)])

        del a
        gc.collect()
        s.emit(Source.signal1)
        assert (results == [(s, Source.signal1, None)])
