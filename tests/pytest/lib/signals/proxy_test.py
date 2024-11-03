# -*- coding: utf-8 -*-

import gc
import threading
import typing

import pytest

from pyknic.lib.signals.extra import CallbackWrapper
from pyknic.lib.signals.proto import Signal, SignalCallbackType, SignalSourceProto, SignalProxyProto
from pyknic.lib.signals.source import SignalSource
from pyknic.lib.tasks.threaded_task import ThreadedTask

from pyknic.lib.signals.proxy import SignalProxy, QueueProxy, QueueProxyStateError, QueueCallbackException


def test_exceptions() -> None:
    assert(issubclass(QueueProxyStateError, Exception) is True)
    assert(issubclass(QueueCallbackException, Exception) is True)


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
            ) -> bool:
                callbacks_registry.callback('test_callback')()
                return True

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


class TestQueueProxy:

    def test_plain(self) -> None:
        queue_proxy = QueueProxy()
        threaded_task = ThreadedTask(queue_proxy)

        threaded_task.start()
        threaded_task.stop()
        threaded_task.join()

        assert(isinstance(queue_proxy, SignalProxyProto))

    def test_signals(self) -> None:
        queue_proxy = QueueProxy()
        threaded_task = ThreadedTask(queue_proxy)
        threaded_task.start()

        class Source(SignalSource):
            signal1 = Signal()
            signal2 = Signal(int)

        lock = threading.Lock()
        results = []

        def callback(source: SignalSourceProto, signal: Signal, value: typing.Any) -> None:
            nonlocal results, lock
            with lock:
                results.append((source, signal, value))

        source1 = Source()
        source2 = Source()

        source1.callback(Source.signal1, queue_proxy.proxy(callback))
        source1.callback(Source.signal2, queue_proxy.proxy(callback))
        source2.callback(Source.signal1, queue_proxy.proxy(callback))

        source1.emit(Source.signal1)
        source1.emit(Source.signal2, 0)
        source2.emit(Source.signal1)
        source2.emit(Source.signal2, 1)

        threaded_task.stop()
        threaded_task.join()

        assert(results == [
            (source1, Source.signal1, None),
            (source1, Source.signal2, 0),
            (source2, Source.signal1, None),
        ])

    def test_exec(self) -> None:
        queue_proxy = QueueProxy()
        threaded_task = ThreadedTask(queue_proxy)
        clbk_event = threading.Event()

        assert(queue_proxy.is_running() is False)

        threaded_task.start()

        def callback() -> None:
            nonlocal clbk_event
            clbk_event.set()

        queue_proxy.exec(callback)
        clbk_event.wait()
        assert(queue_proxy.is_running() is True)

        threaded_task.stop()
        threaded_task.join()
        assert(queue_proxy.is_running() is False)

    def test_exec_wait(self) -> None:
        queue_proxy = QueueProxy()
        callback_result = object()
        threaded_task = ThreadedTask(queue_proxy)
        threaded_task.start()

        def callback() -> object:
            nonlocal callback_result
            return callback_result

        assert(queue_proxy.exec(callback, blocking=True) is callback_result)

        threaded_task.stop()
        threaded_task.join()

    def test_exec_wait_exception(self) -> None:
        queue_proxy = QueueProxy()
        callback_exception = ValueError('!')
        threaded_task = ThreadedTask(queue_proxy)
        threaded_task.start()

        def callback() -> None:
            nonlocal callback_exception
            raise callback_exception

        with pytest.raises(QueueCallbackException):
            queue_proxy.exec(callback, blocking=True)

        try:
            queue_proxy.exec(callback, blocking=True)
        except QueueCallbackException as e:
            assert(e.__cause__ is callback_exception)

        threaded_task.stop()
        threaded_task.join()

    def test_state_exception(self) -> None:
        queue_proxy = QueueProxy()
        threaded_task = ThreadedTask(queue_proxy)

        with pytest.raises(QueueProxyStateError):
            queue_proxy.stop()

        with pytest.raises(QueueProxyStateError):
            queue_proxy.exec(lambda: None)

        threaded_task.start()

        with pytest.raises(QueueProxyStateError):
            queue_proxy.start()

        threaded_task.stop()
        threaded_task.join()

        with pytest.raises(QueueProxyStateError):
            queue_proxy.exec(lambda: None)

        with pytest.raises(QueueProxyStateError):
            queue_proxy.stop()

        with pytest.raises(QueueProxyStateError):
            queue_proxy.start()
