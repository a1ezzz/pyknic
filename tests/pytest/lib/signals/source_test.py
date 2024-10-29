# -*- coding: utf-8 -*-

import typing
import pytest

from pyknic.lib.signals.proto import Signal, SignalSourceProto, UnknownSignalException
from pyknic.lib.signals.source import SignalSourceMeta, SignalSource

from pyknic.lib.x_mansion import CapabilitiesAndSignals


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

    @pytest.mark.parametrize(
        "test_cls", [
            SignalSource,
            CapabilitiesAndSignals,
        ]
    )
    def test(self, test_cls: typing.Type[SignalSource]) -> None:
        source = test_cls()
        assert(isinstance(source, SignalSource) is True)
        assert(isinstance(source, SignalSourceProto) is True)

        pytest.raises(UnknownSignalException, source.emit, Signal())
        pytest.raises(UnknownSignalException, source.callback, Signal(), lambda: None)
        pytest.raises(UnknownSignalException, source.remove_callback, Signal(), lambda: None)

    @pytest.mark.parametrize(
        "test_cls", [
            SignalSource,
            CapabilitiesAndSignals,
        ]
    )
    def test_emit(self, test_cls: typing.Type[SignalSource]) -> None:

        class Source(test_cls):  # type: ignore[valid-type, misc]  # mypy issues will be fixed in future releases
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

    @pytest.mark.parametrize(
        "test_cls", [
            SignalSource,
            CapabilitiesAndSignals,
        ]
    )
    def test_bounded_callbacks(self, test_cls: typing.Type[SignalSource]) -> None:

        class Source(test_cls):  # type: ignore[valid-type, misc]  # mypy issues will be fixed in future releases
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
