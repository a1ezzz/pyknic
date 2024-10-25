# -*- coding: utf-8 -*-

import gc
import typing
import pytest

from pyknic.lib.signals.proto import SignalSourceProto, Signal
from pyknic.lib.signals.source import SignalSource
from pyknic.lib.signals.extra import BoundedCallback, CallbackWrapper


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


class TestCallbackWrapper:

    @pytest.mark.parametrize(
        "weak_ref, callback_called", [
            (None, True),
            (False, True),
            (True, False),
        ]
    )
    def test(
        self,
        signals_registry: 'SignalsRegistry',  # type: ignore[name-defined]  # noqa: F821  # conftest issue
        weak_ref: bool,
        callback_called: bool
    ) -> None:

        class CallbackCls:

            def __call__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
                signals_registry(*args, **kwargs)

        callback_obj = CallbackCls()
        callback_wrapper = CallbackWrapper.wrapper(callback_obj, weak_callback=weak_ref)

        callback_result = [(None, None, None)]

        callback_wrapper(None, None, None)  # type: ignore[arg-type]  # it's just a test
        assert(signals_registry.dump(True) == callback_result)

        del callback_obj
        gc.collect()
        callback_wrapper(None, None, None)  # type: ignore[arg-type]  # it's just a test
        if callback_called:
            assert (signals_registry.dump(True) == callback_result)
        else:
            assert(signals_registry.dump(True) == [])  # since signal_proxy is collected
