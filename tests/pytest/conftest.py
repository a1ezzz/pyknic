# -*- coding: utf-8 -*-

import threading
import typing
import pytest

from pyknic.lib.signals.proto import SignalSourceProto, Signal


class CallbackRegistry:

    def __init__(self) -> None:
        self.__lock: typing.Optional[threading.Lock] = None
        self.__calls: typing.Dict[typing.Hashable, int] = dict()

    def thread_safe(self) -> None:
        assert(not self.__lock)
        self.__lock = threading.Lock()

    def callback(self, callback_id: typing.Hashable = None, callback_result: typing.Any = None) -> 'CallbackCall':
        return CallbackCall(self, callback_id, callback_result)

    def calls(self, callback_id: typing.Hashable = None) -> int:
        return self.__calls.get(callback_id, 0)

    def total_calls(self) -> int:
        return sum(self.__calls.values())

    def register_call(self, callback_id: typing.Hashable = None) -> None:
        def increase() -> None:
            cnt = self.__calls.setdefault(callback_id, 0)
            self.__calls[callback_id] = (cnt + 1)

        if self.__lock:
            with self.__lock:
                increase()
        else:
            increase()


class CallbackCall:

    def __init__(self, registry: CallbackRegistry, callback_id: typing.Hashable, result: typing.Any = None):
        self.__registry = registry
        self.__callback_id = callback_id
        self.__result = result

    def __call__(self, *args: typing.Any, **kwargs: typing.Any) -> typing.Any:
        self.__registry.register_call(self.__callback_id)
        if callable(self.__result):
            return self.__result()
        return self.__result


class SignalsRegistry:

    def __init__(self) -> None:
        self.__lock: typing.Optional[threading.Lock] = None
        self.__calls: typing.List[typing.Tuple[SignalSourceProto, Signal, typing.Any]] = list()

    def thread_safe(self) -> None:
        assert(not self.__lock)
        self.__lock = threading.Lock()

    def flush(self) -> None:
        self.__calls.clear()

    def __call__(self, source: SignalSourceProto, signal: Signal, signal_value: typing.Any) -> None:
        if not self.__lock:
            self.__calls.append((source, signal, signal_value))
        else:
            with self.__lock:
                self.__calls.append((source, signal, signal_value))

    def dump(self, flush: bool = False) -> typing.List[typing.Tuple[SignalSourceProto, Signal, typing.Any]]:
        result = self.__calls.copy()
        if flush:
            self.flush()
        return result


@pytest.fixture
def callbacks_registry(request: pytest.FixtureRequest) -> CallbackRegistry:
    return CallbackRegistry()


@pytest.fixture
def signals_registry(request: pytest.FixtureRequest) -> SignalsRegistry:
    return SignalsRegistry()
