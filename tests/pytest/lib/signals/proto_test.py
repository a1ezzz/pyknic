# -*- coding: utf-8 -*-

import typing
import pytest

from pyknic.lib.signals.proto import Signal, UnknownSignalException, SignalSourceProto, SignalCallbackProto


def test_exceptions() -> None:
    assert(issubclass(UnknownSignalException, Exception) is True)


def test_abstract() -> None:
    pytest.raises(TypeError, SignalSourceProto)
    pytest.raises(NotImplementedError, SignalSourceProto.emit, None, Signal())
    pytest.raises(NotImplementedError, SignalSourceProto.callback, None, Signal(), lambda: None)
    pytest.raises(NotImplementedError, SignalSourceProto.remove_callback, None, Signal(), lambda: None)

    pytest.raises(TypeError, SignalCallbackProto)
    pytest.raises(NotImplementedError, SignalCallbackProto.__call__, None, None, Signal())


class TestSignal:

    def test(self) -> None:
        signal = Signal()
        _ = {signal: 1}  # check that signals may be used as dict keys
        assert(signal != Signal())
        assert(signal == signal)

        assert(repr(signal) == object.__repr__(signal))

        signal.__pyknic_signal_name__ = 'foo'
        assert (repr(signal) == 'foo')

        signal.__pyknic_signal_name__ = 'bar'
        assert (repr(signal) == 'bar')

    @pytest.mark.parametrize('signal_args,signal_value,exc', [
        (tuple(), 1, None),
        (tuple(), 'foo', None),
        ((int, ), 1, None),
        ((int, ), 'foo', TypeError),
        ((int, lambda x: x < 10), 1, None),
        ((int, lambda x: x > 10), 1, ValueError),
    ])
    def test_check(
        self, signal_args: typing.Tuple[typing.Any], signal_value: typing.Any, exc: typing.Optional[typing.Any]
    ) -> None:
        signal = Signal(*signal_args)
        if exc:
            with pytest.raises(exc):
                signal.check_value(signal_value)
        else:
            signal.check_value(signal_value)  # raises nothing
