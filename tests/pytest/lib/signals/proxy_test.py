# -*- coding: utf-8 -*-
import gc
import typing

from pyknic.lib.signals.extra import CallbackWrapper
from pyknic.lib.signals.proto import Signal, SignalCallbackType, SignalSourceProto
from pyknic.lib.signals.source import SignalSource
from pyknic.lib.signals.proxy import SignalProxy


class TestSignalProxy:

    def test(
        self,
        signals_registry: 'SignalsRegistry'  # type: ignore[name-defined]  # noqa: F821  # conftest issue
    ) -> None:
        class Source(SignalSource):
            signal1 = Signal()

        signal_proxy = SignalProxy()
        source = Source()
        source.callback(Source.signal1, signal_proxy.proxy(signals_registry))

        source.emit(Source.signal1)
        assert(signals_registry.dump(True) == [
            (source, Source.signal1, None),
        ])

        signal_proxy.discard_proxy(signals_registry)
        source.emit(Source.signal1)
        assert(signals_registry.dump(True) == [])

    def test_default_wrapper(
        self,
        signals_registry: 'SignalsRegistry'  # type: ignore[name-defined]  # noqa: F821  # conftest issue
    ) -> None:
        class Source(SignalSource):
            signal1 = Signal()

        class CallbackCls:

            def __call__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
                signals_registry(*args, **kwargs)

        signal_proxy = SignalProxy()
        source = Source()
        callback_obj = CallbackCls()
        source.callback(Source.signal1, signal_proxy.proxy(callback_obj))

        source.emit(Source.signal1)
        assert (signals_registry.dump(True) == [
            (source, Source.signal1, None),
        ])

        del callback_obj
        gc.collect()
        source.emit(Source.signal1)
        assert(signals_registry.dump(True) == [])  # since signal_proxy is collected

    def test_custom_wrapper(
        self,
        signals_registry: 'SignalsRegistry',  # type: ignore[name-defined]  # noqa: F821  # conftest issue
        callbacks_registry: 'CallbackRegistry'  # type: ignore[name-defined]  # noqa: F821  # conftest issue
    ) -> None:

        class Source(SignalSource):
            signal1 = Signal()

        class CustomCallbackWrapper(CallbackWrapper):

            def _pre_hook(
                self, callback: SignalCallbackType, source: SignalSourceProto, signal: Signal, value: typing.Any
            ) -> None:
                callbacks_registry.callback('test_callback')()

        signal_proxy = SignalProxy(wrapper_factory=CustomCallbackWrapper)
        source = Source()
        source.callback(Source.signal1, signal_proxy.proxy(signals_registry))

        assert(callbacks_registry.calls('test_callback') == 0)
        source.emit(Source.signal1)
        assert(signals_registry.dump(True) == [
            (source, Source.signal1, None),
        ])
        assert(callbacks_registry.calls('test_callback') == 1)

        signal_proxy.discard_proxy(signals_registry)
        source.emit(Source.signal1)
        assert(signals_registry.dump(True) == [])
        assert(callbacks_registry.calls('test_callback') == 1)
