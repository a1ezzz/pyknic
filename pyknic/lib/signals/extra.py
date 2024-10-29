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

    @verify_value(callback=lambda x: hasattr(x, '__self__'))
    @verify_value(callback=lambda x: getattr(x.__self__, x.__name__) == x)
    def __init__(self, callback: SignalCallbackType):
        """ Create a bounded callback

        :param callback: a function to call
        """
        self.__callback_self = weakref.ref(
            callback.__self__  # type: ignore[attr-defined]  # callback may have __self__
        )
        self.__callback_name = callback.__name__

    def __call__(self, source: SignalSourceProto, signal: Signal, value: typing.Any) -> None:
        """ Execute original function
        """
        s = self.__callback_self()
        if s:
            callback = getattr(s, self.__callback_name)
            callback(source, signal, value)


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
    ) -> None:
        """ This method is called before a callback

        :param callback: a callback this wrapper has
        :param source: signal origin
        :param signal: emitted signal
        :param value: value that was emitted with a signal
        """
        pass

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
            self._pre_hook(callback_obj, source, signal, value)
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
