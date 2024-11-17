# -*- coding: utf-8 -*-

import gc
import pytest
import typing

if typing.TYPE_CHECKING:
    # noinspection PyUnresolvedReferences
    from conftest import CallbackRegistry, SignalsRegistry

from pyknic.lib.signals.proto import SignalSourceProto, Signal, SignalCallbackType
from pyknic.lib.signals.source import SignalSource
from pyknic.lib.signals.extra import BoundedCallback, CallbackWrapper, SignalResender, CallbacksHolder
from pyknic.lib.signals.extra import CustomizedCallback, SignalWaiter


class TestBoundedCallback:

    def test(self, callbacks_registry: 'CallbackRegistry') -> None:

        class Source(SignalSource):
            signal1 = Signal()

        class A:

            def callback(self, source: SignalSourceProto, signal: Signal, value: typing.Any) -> None:
                callbacks_registry.callback('test_callback')()

        s = Source()

        b = BoundedCallback(A().callback)
        s.callback(Source.signal1, b)  # this is ok, but callback will not be executed
        # since 'A()' will be collected
        gc.collect()
        s.emit(Source.signal1)
        assert(callbacks_registry.calls('test_callback') == 0)

        a = A()
        b = BoundedCallback(a.callback)
        s.callback(Source.signal1, b)  # this is ok totally
        gc.collect()
        s.emit(Source.signal1)
        assert(callbacks_registry.calls('test_callback') == 1)

        del a
        gc.collect()
        s.emit(Source.signal1)
        assert(callbacks_registry.calls('test_callback') == 1)

    def test_private_method(self, callbacks_registry: 'CallbackRegistry') -> None:
        class Source(SignalSource):
            signal = Signal()

        class Callback:

            def __init__(self) -> None:
                self.__bounded_callback = BoundedCallback(self.__callback)

            def __callback(self, source: SignalSourceProto, signal: Signal, value: typing.Any) -> None:
                callbacks_registry.callback('test_callback')()

            def register(self, source: Source) -> None:
                source.callback(Source.signal, self.__bounded_callback)

        s = Source()
        c = Callback()
        c.register(s)
        s.emit(Source.signal)
        assert(callbacks_registry.calls('test_callback') == 1)

        del c
        gc.collect()
        s.emit(Source.signal)
        assert(callbacks_registry.calls('test_callback') == 1)


class TestCallbackWrapper:

    @pytest.mark.parametrize(
        "weak_ref, callback_called", [
            (None, True),
            (False, True),
            (True, False),
        ]
    )
    def test(self, signals_registry: 'SignalsRegistry', weak_ref: bool, callback_called: bool) -> None:

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

    def test_hooks(self, signals_registry: 'SignalsRegistry') -> None:

        increment_value = 0

        class CallbackCls:

            def __call__(self, source: SignalSourceProto, signal: Signal, value: typing.Any) -> None:
                nonlocal increment_value
                increment_value += 1
                signals_registry(source, signal, increment_value)

        class CustomWrapper(CallbackWrapper):

            def _pre_hook(
                self, callback: SignalCallbackType, source: SignalSourceProto, signal: Signal, value: typing.Any
            ) -> bool:
                nonlocal increment_value
                increment_value += 1
                signals_registry(source, signal, {"callback": callback, "value": increment_value, "mode": "pre"})
                return True

            def _post_hook(
                self, callback: SignalCallbackType, source: SignalSourceProto, signal: Signal, value: typing.Any
            ) -> None:
                nonlocal increment_value
                increment_value += 1
                signals_registry(source, signal, {"callback": callback, "value": increment_value, "mode": "post"})

        callback_obj = CallbackCls()
        callback_wrapper = CustomWrapper.wrapper(callback_obj, weak_callback=True)

        callback_wrapper(None, None, None)  # type: ignore[arg-type]  # it's just a test
        assert(signals_registry.dump(True) == [
            (None, None, {"callback": callback_obj, "value": 1, "mode": "pre"}),
            (None, None, 2),
            (None, None, {"callback": callback_obj, "value": 3, "mode": "post"}),
        ])

        del callback_obj
        gc.collect()
        callback_wrapper(None, None, None)  # type: ignore[arg-type]  # it's just a test
        assert(signals_registry.dump(True) == [])

    def test_pre_hook(self, signals_registry: 'SignalsRegistry') -> None:

        class CallbackCls:

            def __call__(self, source: SignalSourceProto, signal: Signal, value: typing.Any) -> None:
                signals_registry(source, signal, value)

        class CustomWrapper(CallbackWrapper):

            def _pre_hook(
                self, callback: SignalCallbackType, source: SignalSourceProto, signal: Signal, value: typing.Any
            ) -> bool:
                signals_registry(source, signal, "pre")
                return False

            def _post_hook(
                self, callback: SignalCallbackType, source: SignalSourceProto, signal: Signal, value: typing.Any
            ) -> None:
                signals_registry(source, signal, "post")

        callback_obj = CallbackCls()
        callback_wrapper = CustomWrapper.wrapper(callback_obj, weak_callback=True)

        callback_wrapper(None, None, None)  # type: ignore[arg-type]  # it's just a test
        assert(signals_registry.dump(True) == [
            (None, None, "pre"),
        ])


class TestSignalResender:

    def test_plain(self, signals_registry: 'SignalsRegistry') -> None:
        class Source(SignalSource):
            signal = Signal()

        source1 = Source()
        source2 = Source()
        source2.callback(Source.signal, signals_registry)

        resender = SignalResender(source2)
        source1.callback(Source.signal, resender)
        source1.emit(Source.signal)  # source1 emitted, source2 re-emitted
        assert(signals_registry.dump(True) == [
            (source2, Source.signal, None),
        ])

    def test_different_signal(self, signals_registry: 'SignalsRegistry') -> None:

        class Source1(SignalSource):
            signal = Signal()

        class Source2(SignalSource):
            signal = Signal()

        source1 = Source1()
        source2 = Source2()
        source2.callback(Source2.signal, signals_registry)

        resender = SignalResender(source2, target_signal=Source2.signal)
        source1.callback(Source1.signal, resender)
        source1.emit(Source1.signal)  # source1 emitted, source2 re-emitted
        assert(signals_registry.dump(True) == [
            (source2, Source2.signal, None),
        ])

    def test_weak(self, signals_registry: 'SignalsRegistry') -> None:

        class Source(SignalSource):
            signal = Signal()

        source1 = Source()
        source2 = Source()
        source2.callback(Source.signal, signals_registry)

        resender = SignalResender(source2, Source.signal, weak_target=True)  # noqa: F841  # it must be so
        source1.callback(Source.signal, resender)
        del source2
        gc.collect()
        source1.emit(Source.signal)  # source1 emitted, source2 re-emitted
        assert(signals_registry.dump(True) == [])

    def test_value_converter(self, signals_registry: 'SignalsRegistry') -> None:
        class Source1(SignalSource):
            signal = Signal()

        class Source2(SignalSource):
            signal = Signal(SignalSourceProto)

        source1 = Source1()
        source2 = Source2()
        source2.callback(Source2.signal, signals_registry)

        def value_converter(source: SignalSourceProto, signal: Signal, value: typing.Any) -> typing.Any:
            return source

        resender = SignalResender(  # noqa: F841  # it must be so
            source2, Source2.signal, weak_target=True, value_converter=value_converter
        )
        source1.callback(Source1.signal, resender)

        source1.emit(Source1.signal)
        assert(signals_registry.dump(True) == [
            (source2, Source2.signal, source1),
        ])


class TestCallbacksHolder:

    def test(self, callbacks_registry: 'CallbackRegistry') -> None:
        holder = CallbacksHolder()

        class Source(SignalSource):
            signal = Signal()

        class Ref:
            pass

        reference = Ref()
        clbk = callbacks_registry.callback('test-callback')
        source = Source()

        source.callback(Source.signal, holder.keep_callback(lambda src, signal, value: clbk(), reference))
        assert(callbacks_registry.calls('test-callback') == 0)

        source.emit(Source.signal)
        assert(callbacks_registry.calls('test-callback') == 1)

        del reference
        gc.collect()
        source.emit(Source.signal)
        assert(callbacks_registry.calls('test-callback') == 1)


class TestCustomizedCallback:

    def test(self, callbacks_registry: 'CallbackRegistry') -> None:

        def custom_callback(
            source: SignalSourceProto,
            signal: Signal,
            value: typing.Any,
            optional_arg: typing.Optional[str] = None
        ) -> None:
            callbacks_registry.callback(optional_arg)()

        c_callbacks = CustomizedCallback()

        class Source(SignalSource):
            signal1 = Signal()
            signal2 = Signal()

        class Ref:
            pass

        reference1 = Ref()
        reference2 = Ref()
        source = Source()
        source.callback(Source.signal1, c_callbacks.customize(custom_callback, reference1, optional_arg='test-call1'))
        source.callback(Source.signal2, c_callbacks.customize(custom_callback, reference2, optional_arg='test-call2'))

        assert(callbacks_registry.calls('test-call1') == 0)
        assert(callbacks_registry.calls('test-call2') == 0)

        source.emit(Source.signal1)
        assert(callbacks_registry.calls('test-call1') == 1)
        assert(callbacks_registry.calls('test-call2') == 0)

        source.emit(Source.signal2)
        assert(callbacks_registry.calls('test-call1') == 1)
        assert(callbacks_registry.calls('test-call2') == 1)

        del reference1
        gc.collect()

        source.emit(Source.signal1)
        source.emit(Source.signal2)
        assert(callbacks_registry.calls('test-call1') == 1)
        assert(callbacks_registry.calls('test-call2') == 2)


class TestSignalWaiter:

    def test(self) -> None:

        class Source(SignalSource):
            signal = Signal(int)

        source = Source()

        waiter = SignalWaiter(source, Source.signal, timeout=0.1, value_matcher=lambda x: x == 5)
        assert(waiter.wait() is None)

        source.emit(Source.signal, 1)
        assert(waiter.wait() is None)

        source.emit(Source.signal, 5)
        assert(waiter.wait() == SignalWaiter.ReceivedInfo(source, Source.signal, 5))

    def test_context(self) -> None:

        class Source(SignalSource):
            signal = Signal(int)

        source = Source()
        with pytest.raises(TimeoutError):
            with SignalWaiter(source, Source.signal, timeout=0.1, value_matcher=lambda x: x == 5):
                source.emit(Source.signal, 7)

        with SignalWaiter(source, Source.signal, timeout=0.1, value_matcher=lambda x: x == 5):
            source.emit(Source.signal, 5)  # this is ok

    def test_multiple_signals(self) -> None:

        class Source(SignalSource):
            signal1 = Signal()
            signal2 = Signal()

        source1 = Source()
        source2 = Source()

        with SignalWaiter(source1, Source.signal1, timeout=0.1) as w:
            source2.callback(Source.signal2, w)
            source1.emit(Source.signal1)  # is ok

        with SignalWaiter(source1, Source.signal1, timeout=0.1) as w:
            source2.callback(Source.signal2, w)
            source2.emit(Source.signal2)  # is ok

        with pytest.raises(TimeoutError):
            with SignalWaiter(source1, Source.signal1, timeout=0.1) as w:
                source2.callback(Source.signal2, w)
                source1.emit(Source.signal2)  # will fail
