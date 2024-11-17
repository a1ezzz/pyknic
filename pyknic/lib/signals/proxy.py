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


class QueueProxyStateError(Exception):
    """ This exception is raised when requested operation is not suitable in a current queue state
    """
    pass


class QueueCallbackException(Exception):
    """ This exception is raised when executed callback fails with exception
    """
    pass


class QueueProxy(SignalProxy, TaskProto):
    """ This "proxy" helps to execute "proxified" callbacks in a dedicated thread
    """

    class Item:
        """ This class represent a single callable item in a queue
        """

        def __init__(self, fn: typing.Callable[[], typing.Any]):
            """ Create new item for a queue
            """

            self.__fn = fn
            self.__wait_event = threading.Event()
            self.__result = None
            self.__raised_exception: typing.Optional[BaseException] = None

        def __call__(self) -> None:
            """ Execute a callback and check result
            """
            try:
                self.__result = self.__fn()
            except BaseException as e:
                self.__raised_exception = e
            self.__wait_event.set()

        def wait(self, timeout: typing.Union[int, float, None] = None) -> typing.Any:
            """ Wait for a callback result

            :param timeout: timeout with which a result will be awaited. If the timeout is None then wait forever
            """
            self.__wait_event.wait(timeout)
            if self.__raised_exception:
                raise QueueCallbackException('Callback completed with an exception') from self.__raised_exception
            return self.__result

    class Wrapper(CallbackWrapper):
        """ Alternate :class:`.CallbackWrapper` implementation that work in conjunction with the :class:`.QueueProxy`
        """

        def __init__(self, callback: SignalCallbackType, weak_callback: bool = False):
            """ Create a new wrapper

            :param callback: same as 'callback' in :meth:`.CallbackWrapper.__init__` method
            :param weak_callback: same as 'weak_callback' in :meth:`.CallbackWrapper.__init__` method
            """
            CallbackWrapper.__init__(self, callback, weak_callback=weak_callback)

            self.__queue: typing.Optional[queue.Queue[QueueProxy.Item]] = None
            self.__stop_event: typing.Optional[threading.Event] = None

        def setup_wrapper(
            self,
            queue_value: queue.Queue['QueueProxy.Item'],
            stop_event: threading.Event
        ) -> None:
            """ Setup this wrapper. Without this setup a wrapper will crash
            """
            assert(not self.__queue)
            assert(not self.__stop_event)

            self.__queue = queue_value
            self.__stop_event = stop_event

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
            assert(self.__stop_event)

            if not self.__stop_event.is_set():
                self.__queue.put(QueueProxy.Item(functools.partial(
                    callback, source=source, signal=signal, value=value
                )))  # type: ignore[call-arg]  # mypy issue with functools.partial
            return False

    def __init__(self, flash_flush: bool = False) -> None:
        """ Create a new proxy

        :param flash_flush: if True then every submitted callback will be executed just before the stop event.
        Such callbacks may be omitted otherwise
        """
        SignalProxy.__init__(self, wrapper_factory=QueueProxy.Wrapper)
        TaskProto.__init__(self)

        self.__queue: queue.Queue[QueueProxy.Item] = queue.Queue()

        self.__start_once_lock = threading.Lock()
        self.__stop_once_lock = threading.Lock()
        self.__started_thread: typing.Optional[threading.Thread] = None
        self.__stop_event = threading.Event()
        self.__flash_flush = flash_flush

    def exec(
        self,
        fn: typing.Callable[[], typing.Any],
        blocking: bool = False,
        timeout: typing.Union[int, float, None] = None
    ) -> typing.Any:
        """ Execute a function inside a queue-thread

        :param fn: a callable to execute
        :param blocking: if True then the function result will be awaited
        :param timeout: timeout with which a result should be awaited. This parameter takes effect only when
        the "blocking" parameter is True
        """
        if self.__started_thread is None or self.__stop_event.is_set():
            raise QueueProxyStateError(
                'The "exec" method of the QueueProxy class may be called only if the QueueProxy is running'
            )

        queue_item = QueueProxy.Item(fn)
        self.__queue.put(queue_item)
        if blocking:
            return queue_item.wait(timeout)

    def proxy(self, callback: SignalCallbackType) -> SignalCallbackType:
        """ The :meth:`.SignalProxyProto.proxy` method implementation
        """
        callback_wrapper: QueueProxy.Wrapper = \
            SignalProxy.proxy(  # type: ignore[assignment]  # the SignalProxy.proxy method will return Wrapper
                self, callback
            )

        callback_wrapper.setup_wrapper(self.__queue, self.__stop_event)
        return callback_wrapper

    def __flush(self) -> None:
        """ Execute all the functions that have been stored in the queue
        """
        callback = self.__queue.get(False)
        while callback:
            # with the False value
            if not self.__flash_flush:
                callback()
            self.__queue.task_done()
            callback = self.__queue.get(False)

    def is_running(self) -> bool:
        """ Return True if this queue is running and may accept items and return False otherwise
        """
        return self.__started_thread is not None and not self.__stop_event.is_set()

    def start(self) -> None:
        """ The :meth:`.TaskProto.start` method implementation
        """
        with self.__start_once_lock:
            if self.__started_thread is not None:
                raise QueueProxyStateError("Unable to start QueueProxy twice")
            self.__started_thread = threading.current_thread()

        while not self.__stop_event.is_set():
            next_callback = self.__queue.get()
            next_callback()
            self.__queue.task_done()

        self.__flush()

    def stop(self) -> None:
        """ The :meth:`.TaskProto.stop` method implementation
        """

        with self.__start_once_lock:
            if self.__started_thread is None:
                raise QueueProxyStateError("QueueProxy hasn't started yet")

        lock_acquire = self.__stop_once_lock.acquire(False)
        if lock_acquire:
            self.__stop_event.set()
            self.__queue.put(QueueProxy.Item(lambda: None))  # force the "self.__queue.get()" to return something
            self.__queue.join()
        else:
            raise QueueProxyStateError("QueueProxy can not br stopped twice")

    def is_inside(self) -> bool:
        """ This method helps to find whether current stack is inside started queue or not

        :return: return True if this function is called from the same thread as original :meth:`.QueueProxy.start`
        method is running
        """
        return self.__started_thread is threading.current_thread()
