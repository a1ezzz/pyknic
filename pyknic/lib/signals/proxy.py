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

import functools
import threading
import typing
import queue
import weakref


from pyknic.lib.signals.proto import SignalCallbackType, SignalProxyProto, SignalSourceProto, Signal
from pyknic.lib.signals.extra import CallbackWrapper

from pyknic.lib.tasks.proto import TaskProto


class SignalProxy(SignalProxyProto):
    """ This is a simple :class:`.SignalProxyProto` implementation
    """

    def __init__(self, wrapper_factory: typing.Optional[type[CallbackWrapper]] = None):
        """ Create a new proxy

        :param wrapper_factory: a class is used as a callback wrapper
        """
        SignalProxyProto.__init__(self)
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


class QueueProxy(SignalProxy, TaskProto):
    """ This "proxy" helps to execute "proxified" callbacks in a dedicated thread
    """

    class QueueWrapper(CallbackWrapper):
        """ Alternate :class:`.CallbackWrapper` implementation that work in conjunction with the :class:`.QueueProxy`
        """

        def __init__(self, callback: SignalCallbackType, weak_callback: bool = False):
            """ Create a new wrapper

            :param callback: same as 'callback' in :meth:`.CallbackWrapper.__init__` method
            :param weak_callback: same as 'weak_callback' in :meth:`.CallbackWrapper.__init__` method
            """
            CallbackWrapper.__init__(self, callback, weak_callback=weak_callback)

            self.__queue: typing.Optional[queue.Queue[typing.Callable[[], None]]] = None
            self.__running: typing.Optional[threading.Event] = None

        def setup_wrapper(
            self,
            queue_value: queue.Queue[typing.Callable[[], None]],
            running_event: threading.Event
        ) -> None:
            """ Setup this wrapper. Without this setup a wrapper will crash
            """
            assert(not self.__queue)
            assert(not self.__running)

            self.__queue = queue_value
            self.__running = running_event

        def _pre_hook(
            self, callback: SignalCallbackType, source: SignalSourceProto, signal: Signal, value: typing.Any
        ) -> bool:
            """ This pre-hook always returns False (a callback will be skipped from follow-on execution) and submits
            the callback to a queue inside a :class:`.QueueProxy` object

            :param callback: a callback that is proxying
            :param source: signal origin
            :param signal: emitted signal
            :param value: a value of an emitted signal
            """
            assert(self.__queue)
            assert(self.__running)

            if self.__running.is_set():
                self.__queue.put(functools.partial(callback, source, signal, value))
            return False

    def __init__(self, flash_flush: bool = False) -> None:
        """ Create a new proxy

        :param flash_flush: if True then every submitted callback will be executed just before the stop event.
        Such callbacks may be omitted otherwise
        """
        SignalProxy.__init__(self, wrapper_factory=QueueProxy.QueueWrapper)
        TaskProto.__init__(self)

        self.__queue: queue.Queue[typing.Callable[[], None]] = queue.Queue()

        self.__running = threading.Event()
        self.__flash_flush = flash_flush

    def proxy(self, callback: SignalCallbackType) -> SignalCallbackType:
        """ The :meth:`.SignalProxyProto.proxy` method implementation
        """
        callback_wrapper: QueueProxy.QueueWrapper = \
            SignalProxy.proxy(  # type: ignore[assignment]  # the SignalProxy.proxy method will return QueueWrapper
                self, callback
            )

        callback_wrapper.setup_wrapper(self.__queue, self.__running)
        return callback_wrapper

    def __flush(self) -> None:
        """ Execute all the functions that have been stored in the queue
        """
        callback = self.__queue.get(False)
        while callback:  # type: ignore[truthy-function]  # mypy is incorrect here since the get method is called
            # with the False value
            if not self.__flash_flush:
                callback()
            self.__queue.task_done()
            callback = self.__queue.get(False)

    def start(self) -> None:
        """ The :meth:`.TaskProto.start` method implementation
        """
        self.__running.set()
        while self.__running.is_set():
            next_callback = self.__queue.get()
            next_callback()
            self.__queue.task_done()

        self.__flush()

    def stop(self) -> None:
        """ The :meth:`.TaskProto.stop` method implementation
        """
        self.__running.clear()
        self.__queue.put(lambda: None)  # force the "self.__queue.get()" to return something
        self.__queue.join()
