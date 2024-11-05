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

import typing
import weakref

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
            target.emit(sig, self.__converter(source, signal, value))
