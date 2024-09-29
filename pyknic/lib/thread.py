# -*- coding: utf-8 -*-
# pyknic/lib/thread.py
#
# Copyright (C) 2017-2024 the pyknic authors and contributors
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
import types
import typing

import decorator
from pyknic.lib.typing import GenericFunc, P, R


class CriticalSectionError(Exception):
    """ An exception that may be raised if a lock for a critical section could not be acquired
    """
    pass


def acquire_lock(lock: threading.Lock, timeout: typing.Union[int, float, None] = None) -> bool:
    """ This function overload the original :meth:`.Lock.acquire` method that has two arguments ('blocking'
    and 'timeout') with the one argument only - 'timeout'. This argument may be set to None now

    :param lock: a lock that should be gained

    :param timeout: timeout that this function should wait in order to gain a lock. If the "timeout" is not
    specified (is None) then wait forever in a blocking mode till a lock is gained, if the "timeout" is a
    positive value this is a period of time in seconds that this function will wait for a lock in a blocking mode.
    If a non-positive value is set then this function will return immediately even if lock was not gained
    :type timeout: int | float | None

    :return: whether a specified lock is gained or not
    """
    if timeout is None:
        blocking = True
        timeout = -1
    elif timeout <= 0:
        blocking = False
        timeout = -1
    else:
        blocking = True
    return lock.acquire(blocking=blocking, timeout=timeout)


def critical_section_dynamic_lock(
    lock_fn: typing.Callable[..., threading.Lock],
    timeout_fn: typing.Optional[typing.Callable[..., typing.Union[int, float, None]]] = None
) -> typing.Callable[[GenericFunc[P, R]], GenericFunc[P, R]]:
    """ Protect a function with a lock, that was get from the specified function. If a lock can not be acquired, then
    no function call will be made

    :param lock_fn: callable that returns a lock, with which a function may be protected
    :param timeout_fn: callable that returns a timeout that is used the same way as the 'timeout' in
    the :func:`.acquire_lock` function

    :return: decorator with which a target function may be protected
    """

    def first_level_decorator(
        decorated_function: typing.Callable[..., typing.Any]
    ) -> typing.Callable[..., typing.Any]:
        def second_level_decorator(
            original_function: typing.Callable[..., typing.Any], *args: typing.Any, **kwargs: typing.Any
        ) -> typing.Any:
            lock = lock_fn(*args, **kwargs)
            timeout = timeout_fn(*args, **kwargs) if timeout_fn else None
            if acquire_lock(lock, timeout=timeout) is True:
                try:
                    result = original_function(*args, **kwargs)
                    return result
                finally:
                    lock.release()

            raise CriticalSectionError('Unable to lock a critical section')

        return decorator.decorator(second_level_decorator)(decorated_function)
    return first_level_decorator


def critical_section_lock(
    lock: threading.Lock, timeout: typing.Union[int, float, None] = None
) -> typing.Callable[[GenericFunc[P, R]], GenericFunc[P, R]]:
    """ A wrapper for :func:`.critical_section_dynamic_lock` function call, but with a static lock and timeout objects
    instead of functions

    :param lock: lock with which a function will be protected
    :param timeout: timeout for acquiring lock

    :return: decorator with which a target function may be protected
    """

    def lock_getter(*args: typing.Any, **kwargs: typing.Any) -> threading.Lock:
        return lock

    def timeout_getter(*args: typing.Any, **kwargs: typing.Any) -> typing.Union[int, float, None]:
        return timeout

    return critical_section_dynamic_lock(lock_fn=lock_getter, timeout_fn=timeout_getter)


class CriticalResource:
    """ Class for simplifying thread safety for a shared object. Each class instance holds its own lock object
    that :meth:`.CriticalResource.critical_section` method will be used to protect bounded methods.
    Bounded methods are allowed to be protected only. Static methods or class methods are unsupported
    """

    class LockFreeContext:
        """ This class may be used as a context that gets a monopoly access to a critical resource
        (an :class:`.CriticalResource` object) and all the methods of that resource won't try to access already
        gained lock and won't cause a deadlock.

        :note: this object doesn't protect itself from a race condition. So this object usage must be limited to a
        single thread only
        """

        def __init__(self, critical_resource: 'CriticalResource', timeout: typing.Union[int, float, None] = None):
            """ Create a new context object

            :param critical_resource: resource that this context should access and protect
            :param timeout: the same as 'timeout' in the :func:`.acquire_lock` function
            """

            self.__resource = critical_resource
            self.__timeout = timeout
            self.__unlock = False

        def __getattr__(self, item: str) -> typing.Any:
            """ "Proxy" access to an original resource. If the result is protected by a lock with
            :meth:`.CriticalResource.critical_section` decorator then an original (lock free) method is returned

            :raise CriticalSectionError: if a resource was not locked before this access
            """
            if not self.__unlock:
                raise CriticalSectionError(
                    'A resource access error. A lock to the resource must be gotten at first!'
                )

            r_item = object.__getattribute__(self.__resource, item)

            try:
                return functools.partial(r_item.__pyknic_lock_free_fn__, r_item.__self__)
            except AttributeError:
                pass
            return r_item

        def __enter__(self) -> typing.Self:
            """ Enter this context and lock a resource

            :raise CriticalSectionError: if a resource was not locked during a specified timeout
            """
            if not acquire_lock(self.__resource.thread_lock(), self.__timeout):
                raise CriticalSectionError('Unable to lock a critical section')
            self.__unlock = True
            return self

        def __exit__(
            self,
            exc_type: typing.Optional[typing.Type[BaseException]],
            exc_val: typing.Optional[BaseException],
            exc_tb: typing.Optional[types.TracebackType]
        ) -> None:
            """ Exit a context and release a lock
            """
            if self.__unlock is True:
                self.__unlock = False
                self.__resource.thread_lock().release()

        def __del__(self) -> None:
            """ If a resource is locked still then unlock it
            """
            if self.__unlock is True:
                self.__unlock = False
                self.__resource.thread_lock().release()

    def __init__(self, timeout: typing.Union[int, float, None] = None) -> None:
        """ Create a lock

        :param timeout: the same as 'timeout' in the :func:`.acquire_lock` function
        """
        self.__lock = threading.Lock()
        self.__timeout = timeout

    def thread_lock(self) -> threading.Lock:
        """ Return a lock with which a bounded methods may be protected
        """
        return self.__lock

    def lock_timeout(self) -> typing.Union[int, float, None]:
        return self.__timeout

    def critical_context(self, timeout: typing.Union[int, float, None] = None) -> 'LockFreeContext':
        """ Create a lock free context for this object

        :param timeout: timeout for acquiring lock. the same as 'timeout' in
        the :meth:`.CriticalResource.LockFreeContext.__init__` method
        """
        return CriticalResource.LockFreeContext(self, timeout=timeout)

    @staticmethod
    def critical_section(
        decorated_function: typing.Callable[..., typing.Any]
    ) -> typing.Callable[..., typing.Any]:
        """ Decorate a method with a lock protection (class methods and static methods are unsupported)
        """

        def lock_fn(self: CriticalResource, *args: typing.Any, **kwargs: typing.Any) -> threading.Lock:
            if isinstance(self, CriticalResource) is False:
                raise TypeError(
                    'Invalid object type. It must be inherited from CriticalResource class and'
                    ' decorated method must be bounded'
                )
            return self.thread_lock()

        def timeout_fn(
            self: CriticalResource, *args: typing.Any, **kwargs: typing.Any
        ) -> typing.Union[int, float, None]:
            if isinstance(self, CriticalResource) is False:
                raise TypeError(
                    'Invalid object type. It must be inherited from CriticalResource class and'
                    ' decorated method must be bounded'
                )
            return self.lock_timeout()

        decorated_function.__pyknic_lock_free_fn__ = decorated_function  # type: ignore[attr-defined] # we are force
        # the attribute to be
        return critical_section_dynamic_lock(lock_fn=lock_fn, timeout_fn=timeout_fn)(decorated_function)
