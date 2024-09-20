# -*- coding: utf-8 -*-
# pyknic/lib/signals/source.py
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

# TODO: document the code
# TODO: write tests for the code

import typing

from abc import ABCMeta
from weakref import WeakSet

from pyknic.lib.signals.proto import Signal, SignalSourceProto, UnknownSignalException, SignalCallbackType


class SignalSourceMeta(ABCMeta):
    """ This class helps to manage signals defined for the class
    """

    def __new__(
        mcs,
        name: str,
        bases: typing.Tuple[type],
        namespace: typing.Dict[str, typing.Any], **kwargs: typing.Any
    ) -> type:
        """ Generate new class with this metaclass
        """
        obj = ABCMeta.__new__(mcs, name, bases, namespace, **kwargs)
        obj.__pyknic_signals__ = set()  # type: ignore[attr-defined] # metaclass and mypy issues
        return obj

    def __init__(cls, name: str, bases: typing.Tuple[type], namespace: typing.Dict[str, typing.Any]):
        """ Initialize class with this metaclass
        """
        ABCMeta.__init__(cls, name, bases, namespace)

        for class_attr in dir(cls):
            class_attr_value = ABCMeta.__getattribute__(cls, class_attr)
            if isinstance(class_attr_value, Signal) is True:
                for base_class in bases:
                    try:
                        base_class_attr_value = ABCMeta.__getattribute__(base_class, class_attr)
                        if class_attr_value != base_class_attr_value:
                            raise TypeError(
                                'Signals may not be overridden! Duplicated signal (%s) spotted for the class "%s"'
                                ' (found at the base class %s)'
                                % (class_attr, str(cls), str(base_class))
                            )
                        base_class_attr_value.__pyknic_signal_name__ = f'{base_class.__name__}.{class_attr}'
                    except AttributeError:
                        pass
                if not class_attr_value.__pyknic_signal_name__:
                    class_attr_value.__pyknic_signal_name__ = f'{cls.__name__}.{class_attr}'
                cls.__pyknic_signals__.add(class_attr_value)  # type: ignore[attr-defined] # metaclass and mypy issues


class SignalSource(SignalSourceProto, metaclass=SignalSourceMeta):
    """ :class:`.SignalSourceProto` implementation
    """

    def __init__(self) -> None:
        """ Create new signal source
        """

        SignalSourceProto.__init__(self)
        self.__callbacks: typing.Dict[Signal, WeakSet[SignalCallbackType]] = {
            x: WeakSet() for x in self.__class__.__pyknic_signals__  # type: ignore[attr-defined] # metaclass and mypy
        }

    def emit(self, signal: Signal, signal_value: typing.Any = None) -> None:
        """ :meth:`.SignalSourceProto.emit` implementation
        """
        try:
            callbacks = self.__callbacks[signal]
        except KeyError:
            raise UnknownSignalException('Unknown signal emitted')

        signal.check_value(signal_value)

        for c in callbacks:
            if c is not None:
                c(self, signal, signal_value)

    def callback(self, signal: Signal, callback: SignalCallbackType) -> None:
        """ :meth:`.SignalSourceProto.callback` implementation
        """
        try:
            self.__callbacks[signal].add(callback)
        except KeyError:
            raise UnknownSignalException('Unknown signal subscribed')

    def remove_callback(self, signal: Signal, callback: SignalCallbackType) -> None:
        """ :meth:`.SignalSourceProto.remove_callback` implementation
        """
        try:
            callbacks = self.__callbacks[signal]
            callbacks.remove(callback)
        except KeyError:
            raise UnknownSignalException('Signal does not have the specified callback')
