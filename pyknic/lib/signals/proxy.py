# -*- coding: utf-8 -*-
# pyknic/lib/signals/proxy.py
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

from pyknic.lib.signals.proto import SignalCallbackType, SignalProxyProto
from pyknic.lib.signals.extra import CallbackWrapper


class SignalProxy(SignalProxyProto):
    """ This is a simple :class:`.SignalProxyProto` implementation
    """

    def __init__(self, wrapper_factory: typing.Optional[type[CallbackWrapper]] = None):
        """ Create a new proxy

        :param wrapper_factory: a class is used as a callback wrapper
        """
        self.__callbacks: weakref.WeakValueDictionary[SignalCallbackType, SignalCallbackType] = \
            weakref.WeakValueDictionary()
        self.__wrapper_factory = wrapper_factory if wrapper_factory else CallbackWrapper

    def proxy(self, callback: SignalCallbackType) -> SignalCallbackType:
        """ The :meth:`.SignalProxyProto.proxy` method implementation
        """
        callback_wrapper = self.__wrapper_factory.wrapper(callback, weak_callback=True)
        self.__callbacks[callback_wrapper] = callback
        return callback_wrapper

    def discard_proxy(self, callback: SignalCallbackType) -> None:
        """ The :meth:`.SignalProxyProto.discard_proxy` method implementation
        """
        to_remove = []
        for wrapper, original_callback in self.__callbacks.items():
            if callback is original_callback:
                to_remove.append(wrapper)

        for i in to_remove:
            self.__callbacks.pop(i)
