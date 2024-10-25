# -*- coding: utf-8 -*-
# pyknic/lib/signals/proto.py
#
# Copyright (C) 2019-2024 the pyknic authors and contributors
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

from abc import ABCMeta, abstractmethod
from inspect import isclass, isfunction, ismethod


class Signal:
    """ A signal that may be sent within wasp_general.api.signals methods
    """

    __pyknic_signal_name__: typing.Optional[str] = None

    def __init__(self, *checks: typing.Union[type, typing.Callable[[typing.Any], bool]]):
        """ Create a new (and unique) signal. Every object represent a unique signal

        :param checks: types or callables that signal value (that sent within a signal) must comply. Types are optional
        classes that signal value must be derived from. Callables (functions or methods) check values, each function
        """
        self.__check_types = tuple({x for x in checks if isclass(x)})
        self.__check_functions = tuple({x for x in checks if isfunction(x) or ismethod(x)})

    def check_value(self, value: typing.Any) -> None:
        """ Check value and raise exceptions (TypeError or ValueError) if value is invalid

        :param value: value that is checked whether it may or may not be sent with this signal

        :raises TypeError: if a value's type differ from types that are specified for this signal
        :raises ValueError: if a value's value does not comply with checks functions
        """
        if self.__check_types and isinstance(value, self.__check_types) is False:
            raise TypeError('Signal value is invalid (type mismatch)')
        for c in self.__check_functions:
            if not c(value):
                raise ValueError('Signal value is invalid (value mismatch)')

    def __hash__(self) -> int:
        """ Hash function in order to use this class as a dict key
        """
        return id(self)

    def __eq__(self, other: typing.Any) -> bool:
        """ Comparison function in order to use this class as a dict key
        """
        return id(other) == id(self)

    def __repr__(self) -> str:
        """ Because each signal is unique, it is much simpler to show its identifier in debug messages instead of an
        object's memory location
        """
        if self.__pyknic_signal_name__:
            return self.__pyknic_signal_name__
        return object.__repr__(self)


class SignalSourceProto(metaclass=ABCMeta):
    """ An entry class for an object that sends signals. Every callback is saved as a 'weak' reference. So in most
    cases in order to stop executing callback it is sufficient just to discard all callback's references
    """

    @abstractmethod
    def emit(self, signal: Signal, signal_value: typing.Any = None) -> None:
        """ Send a signal from this object and execute all linked callbacks within the same thread that called
        this function. Since number of callbacks are not limited it is better to use callbacks that postpone execution
        with some kind of "queue" rather than immediately execute a code. That queue may be an asyncio loop, thread pool
        or something similar

        :param signal: a signal (an object) to send
        :param signal_value: a signal argument that may be sent within a signal (this value should be checked first)
        """
        raise NotImplementedError('This method is abstract')

    @abstractmethod
    def callback(
        self,
        signal: Signal,
        callback: typing.Callable[['SignalSourceProto', Signal, typing.Any], None]
    ) -> None:
        """ Register a callback that will be executed when new signal is sent. Callbacks may be (and should be) saved
        as a weak reference so it is a callback responsibility to be alive and not to be collected by the mighty gc.
        If the same callback is registered twice it may be (or might be) called just once, no matter how many times
        it was registered

        :param signal: signal that will trigger a callback
        :param callback: callback that must be executed
        """
        raise NotImplementedError('This method is abstract')

    @abstractmethod
    def remove_callback(
        self,
        signal: Signal,
        callback: typing.Callable[['SignalSourceProto', Signal, typing.Any], None]
    ) -> None:
        """ Unregister the specified callback and prevent it to be executed when new signal is sent

        :param signal: signal that should be avoided by the specified callback
        :param callback: callback that should be unregistered
        """
        raise NotImplementedError('This method is abstract')


class SignalCallbackProto(metaclass=ABCMeta):
    """ An example of class that may receive signals (callback signature)
    """

    @abstractmethod
    def __call__(self, signal_source: SignalSourceProto, signal: Signal, signal_value: typing.Any = None) -> None:
        """ A callback that will be called when a signal is sent

        :param signal_source: origin of a signal
        :param signal: a signal that was sent
        :param signal_value: any argument that you want to pass with the specified signal. A specific signal
        may relay on this argument and may raise an exception if unsupported value is spotted
        """
        raise NotImplementedError('This method is abstract')


class UnknownSignalException(Exception):
    """ This exception may be raised if there was a request to amit an unknown signal. Usually it means that signal
    source is not able to send such signal.
    """
    pass


SignalCallbackType = typing.Callable[[SignalSourceProto, Signal, typing.Any], None]  # shortcut for the signal callback


class SignalProxyProto(metaclass=ABCMeta):
    """ This class works like a factory, which returns wrapper for callbacks
    """

    @abstractmethod
    def proxy(self, callback: SignalCallbackType) -> SignalCallbackType:
        """ Generate a wrapper for a callback and return it

        :param callback: a callback that should be "wrapped"
        :return: a wrapper
        """
        raise NotImplementedError('This method is abstract')

    @abstractmethod
    def discard_proxy(self, callback: SignalCallbackType) -> None:
        """ Disable previously returned wrappers that was generated by a callback

        :param callback: a callback which wrappers should be omitted
        """
        raise NotImplementedError('This method is abstract')
