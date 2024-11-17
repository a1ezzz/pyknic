# -*- coding: utf-8 -*-
# pyknic/lib/signals/extra.py
#
# Copyright (C) 2024 the pyknic authors and contributors
# <see AUTHORS file>
#
# This file is part of pyknic.
#
# pyknic is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# pyknic is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with pyknic.  If not, see <http://www.gnu.org/licenses/>.

import threading
import types
import typing
import weakref

from dataclasses import dataclass

from pyknic.lib.verify import verify_value

from pyknic.lib.signals.proto import SignalSourceProto, SignalCallbackType, Signal


class BoundedCallback:
    """ This class allows to use a bounded method as a signal callback
    """

    @verify_value(callback=lambda x: hasattr(x, '__self__') and hasattr(x, '__func__'))
    def __init__(self, callback: SignalCallbackType):
        """ Create a bounded callback

        :param callback: a function to call
        """
        self.__callback_self = weakref.ref(
            callback.__self__  # type: ignore[attr-defined]  # callback may have __self__
        )
        self.__callback = callback.__func__  # type: ignore[attr-defined]  # callback may have __func__

    def __call__(self, source: SignalSourceProto, signal: Signal, value: typing.Any) -> None:
        """ Execute original function
        """
        s = self.__callback_self()
        if s:
            self.__callback(s, source, signal, value)


class CallbackWrapper:
    """ This is a base class for a simple wrapper factory. Is mostly used by :class:`.SignalProxyProto` implementations
    """

    def __init__(self, callback: SignalCallbackType, weak_callback: bool = False):
        """ Create a new wrapper

        :param callback: original callback to execute
        :param weak_callback: whether a general link or a weak link should be made for a callback
        """
        self.__weak = weak_callback
        self.__callback = weakref.ref(callback) if weak_callback else callback

    def _pre_hook(
        self, callback: SignalCallbackType, source: SignalSourceProto, signal: Signal, value: typing.Any
    ) -> bool:
        """ This method is called before a callback

        :param callback: a callback this wrapper has
        :param source: signal origin
        :param signal: emitted signal
        :param value: value that was emitted with a signal

        :return: True if callback and post hook should be called or False otherwise
        """
        return True

    def __call__(self, source: SignalSourceProto, signal: Signal, value: typing.Any) -> None:
        """ Execute an original callback

        :param source: signal origin
        :param signal: emitted signal
        :param value: value that was emitted with a signal
        """
        callback_obj: SignalCallbackType = (
            self.__callback() if self.__weak else self.__callback  # type: ignore[call-arg, assignment]  # mypy issue
        )
        if callback_obj is not None:
            if self._pre_hook(callback_obj, source, signal, value):
                callback_obj(source, signal, value)
                self._post_hook(callback_obj, source, signal, value)

    def _post_hook(
        self, callback: SignalCallbackType, source: SignalSourceProto, signal: Signal, value: typing.Any
    ) -> None:
        """ This method is called after a callback

        :param callback: a callback this wrapper has
        :param source: signal origin
        :param signal: emitted signal
        :param value: value that was emitted with a signal
        """
        pass

    @classmethod
    def wrapper(cls, callback: SignalCallbackType, weak_callback: bool = False) -> 'CallbackWrapper':
        """ Factory class method that returns class instance

        :param callback: same as the "callback" in the :meth:`.CallbackWrapper.__init__` method
        :param weak_callback: same as the "weak_callback" in the :meth:`.CallbackWrapper.__init__` method
        """
        return cls(callback, weak_callback=weak_callback)


class SignalResender:
    """ This class helps to resend signals with a new origin (and/or signal and/or value =) )
    """

    def __init__(
        self,
        target_source: SignalSourceProto,
        target_signal: typing.Optional[Signal] = None,
        weak_target: bool = False,
        value_converter: typing.Optional[typing.Callable[[SignalSourceProto, Signal, typing.Any], typing.Any]] = None
    ):
        """ Create a callback that re-emits signal with a new origin

        :param target_source: source that will send signal as a new origin
        :param target_signal: signal to send (if not defined then the emitted "signal" will be reused)
        :param weak_target: whether a target reference should be kept as a weak reference
        :param value_converter: this callback (if defined) will translate received signal to a signal's value
        that will be used
        """
        self.__weak_target = weak_target
        self.__target_source = weakref.ref(target_source) if weak_target else target_source
        self.__target_signal = target_signal
        self.__converter = value_converter if value_converter else self.__default_converter

    def __default_converter(self, source: SignalSourceProto, signal: Signal, value: typing.Any) -> typing.Any:
        """ Default converter that returns value as is
        """
        return value

    def __call__(self, source: SignalSourceProto, signal: Signal, value: typing.Any) -> None:
        """ A callback that to the job
        """
        target_src = self.__target_source
        target: SignalSourceProto = (
            target_src() if self.__weak_target else target_src  # type: ignore[operator, assignment]  # mypy issue
        )
        if target is not None:
            sig = self.__target_signal if self.__target_signal else signal
            target.emit(sig, self.__converter(source, sig, value))


class CallbacksHolder:
    """ This class helps to store callbacks with respect to memory
    """

    def __init__(self) -> None:
        """ Create a new holder to store callbacks
        """
        self.__callbacks: weakref.WeakValueDictionary[SignalCallbackType, typing.Any] = weakref.WeakValueDictionary()

    def keep_callback(self, callback: SignalCallbackType, reference_key: typing.Any) -> SignalCallbackType:
        """ Keep a new callback and return it

        :param callback: a callback to store
        :param reference_key: an object. While this object exists a callback exists
        """
        self.__callbacks[callback] = reference_key
        return callback


class CustomizedCallback:
    """ This class helps to call a callback with additional static arguments
    """

    class StaticWrapper:
        """ This is a wrapper for a callback
        """

        def __init__(
            self,
            callback: typing.Callable[[SignalSourceProto, Signal, typing.Any], None],
            **kwargs: typing.Any
        ) -> None:
            """ Create a wrapper

            :param callback: an original callback to call
            :param kwargs: static arguments to use along with the call
            """
            self.__callback = callback
            self.__kwargs = kwargs

        def __call__(self, source: SignalSourceProto, signal: Signal, value: typing.Any) -> None:
            """ Execute an original callback with extra static arguments
            """
            self.__callback(source, signal, value, **self.__kwargs)

    def __init__(self) -> None:
        """ Create a holder that will create callbacks with static arguments
        """
        self.__holder = CallbacksHolder()

    def customize(
        self,
        callback: typing.Callable[[SignalSourceProto, Signal, typing.Any], None],
        reference_key: typing.Any,
        **kwargs: typing.Any
    ) -> SignalCallbackType:
        """ Create and store a new callback

        :param callback: a base callback to use
        :param reference_key: a reference key to store a callback (the same as the "reference_key" parameter
        in the :meth:`.CallbacksHolder.keep_callback` method)
        :param kwargs: static arguments to use with the callback
        """
        custom_callback = CustomizedCallback.StaticWrapper(callback, **kwargs)
        self.__holder.keep_callback(custom_callback, reference_key)
        return custom_callback


class SignalWaiter:
    """ This class helps to wait for a signal
    """

    @dataclass
    class ReceivedInfo:
        source: SignalSourceProto
        signal: Signal
        value: typing.Any

    def __init__(
        self,
        target_source: SignalSourceProto,
        target_signal: Signal,
        timeout: typing.Union[int, float, None] = None,
        event: typing.Optional[threading.Event] = None,
        value_matcher: typing.Optional[typing.Callable[[typing.Any], bool]] = None
    ):
        """ Create object that will wait for a signal and sign up for it

        :param target_source: a source that will be subscribed for a signal to come
        :param target_signal: a signal to await
        :param timeout: timeout with which a result will be awaited. If the timeout is None then wait forever
        :param event: optional event that will be used to wait a signal. If not defined then internal event is used
        :param value_matcher: optional callable that checks received signal value. If defined then
        the event will be set only if this function return True on received signal value
        """
        self.__timeout = timeout
        self.__event = event if event else threading.Event()
        self.__matcher = value_matcher
        self.__received_signal: typing.Optional[SignalWaiter.ReceivedInfo] = None

        target_source.callback(target_signal, self)

    def __enter__(self) -> 'SignalWaiter':
        """ Start a context
        """
        return self

    def __exit__(
        self,
        exc_type: typing.Optional[typing.Type[BaseException]],
        exc_val: typing.Optional[BaseException],
        exc_tb: typing.Optional[types.TracebackType]
    ) -> None:
        """ Exit a context and wait for a signal
        """
        if exc_type is None:
            if self.wait() is None:
                raise TimeoutError("Signal wasn't received in time")

    def __call__(self, source: SignalSourceProto, signal: Signal, value: typing.Any) -> None:
        """ A callback that may be subscribed to more signals to come
        """
        if self.__matcher is None or self.__matcher(value):
            self.__received_signal = SignalWaiter.ReceivedInfo(source, signal, value)
            self.__event.set()

    def wait(self, ) -> typing.Optional['SignalWaiter.ReceivedInfo']:
        """ Wait for a signal and return True if signal has been received or False otherwise
        """
        self.__event.wait(self.__timeout)
        return self.__received_signal
