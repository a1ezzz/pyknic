# -*- coding: utf-8 -*-
# pyknic/lib/thread.py
#
# Copyright (C) 2017-2026 the pyknic authors and contributors
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


import dataclasses
import functools
import inspect
import threading
import types
import typing

import decorator

from pyknic.lib.log import Logger


class CriticalSectionError(Exception):
    """ An exception that may be raised if a lock for a critical section could not be acquired
    """
    pass


class CriticalResource:
    """ Class for simplifying thread safety for a shared object. Each class instance holds its own lock object
    that :meth:`.CriticalResource.critical_section` method will be used to protect bounded methods.
    Bounded methods are allowed to be protected only. Static methods or class methods are unsupported
    """

    @dataclasses.dataclass
    class LockOwner:
        """ This class keeps some extra data that may be helpful to debug self-locking problems
        """
        thread: typing.Optional[threading.Thread] = None  # thread that has acquired a lock
        description: typing.Optional[str] = None          # any details

    class LockFreeContext:
        """ This class may be used as a context that gets a monopoly access to a critical resource
        (an :class:`.CriticalResource` object) and all the methods of that resource won't try to access already
        gained lock and won't cause a deadlock.

        :note: this object doesn't protect itself from a race condition. So this object usage must be limited to a
        single thread only
        """

        def __init__(
            self,
            resource: 'CriticalResource',
            owner: 'CriticalResource.LockOwner',
            main_lock: threading.Lock,
            pre_lock: threading.Lock,
            timeout: typing.Union[int, float, None] = None,
            description: typing.Optional[str] = None
        ):
            """ Create a new context object

            :param resource: resource that this context should access and protect.
            :param owner: an object (ie link to an object) that stores info about current lock owner.
            :param main_lock: this lock protects access to the "resource" object.
            :param pre_lock:  this lock protects access to the "owner" object.
            :param timeout: timeout that this function should wait in order to gain a lock. If the "timeout" is not
            specified (is None) or is a negative value then wait forever in a blocking mode till a lock is gained.
            If the "timeout" is a positive value this is a period of time in seconds that this function will wait for
            a lock in a blocking mode.
            :param description: on a main lock acquisition this description will be stored in an "owner" object.
            """
            self.__resource = resource
            self.__timeout = timeout
            self.__main_lock = main_lock
            self.__pre_lock = pre_lock
            self.__locked = False
            self.__owner = owner
            self.__description = description

        def __getattr__(self, item: str) -> typing.Any:
            """ "Proxy" access to an original resource. If the result is protected by a lock with
            :meth:`.CriticalResource.critical_section` decorator then an original (lock free) method is returned
            """

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

            with self.__pre_lock:
                if self.__owner.thread is threading.current_thread():

                    if self.__timeout is not None and self.__timeout > 0:
                        Logger.warning(
                            f'The same thread is trying to acquire the same lock {repr(self.__main_lock)}!' +
                            (f' Lock acquired by: {self.__owner.description}' if self.__owner.description else '') +
                            (f' Lock requested by: {self.__description}' if self.__description else '') +
                            f' This is OK since the timeout was set ({self.__timeout}) but still'
                        )
                    else:
                        raise CriticalSectionError(
                            f'The same thread is trying to acquire the same lock {repr(self.__main_lock)}!' +
                            (f' Lock acquired by: {self.__owner.description}' if self.__owner.description else '') +
                            (f' Lock requested by: {self.__description}' if self.__description else '')
                        )

            if not self.__main_lock.acquire(timeout=(self.__timeout if self.__timeout is not None else -1)):
                raise CriticalSectionError('Unable to lock a critical section')

            with self.__pre_lock:
                self.__owner.thread = threading.current_thread()
                self.__owner.description = self.__description
                self.__locked = True

            return self

        def __exit__(
            self,
            exc_type: typing.Optional[typing.Type[BaseException]],
            exc_val: typing.Optional[BaseException],
            exc_tb: typing.Optional[types.TracebackType]
        ) -> None:
            """ Exit a context and release a lock
            """

            with self.__pre_lock:
                self.__owner.thread = None
                self.__owner.description = None

            self.__main_lock.release()

            with self.__pre_lock:
                self.__locked = False

        def __del__(self) -> None:
            """ If a resource is locked still then unlock it
            """

            with self.__pre_lock:
                if self.__locked:
                    Logger.warning(
                        f'The object "{repr(self)}" is destroying now, but a lock is locked still!' +
                        (f' Lock acquired by: {self.__owner.description}' if self.__owner.description else '') +
                        ' We will try to release it'
                    )

                    self.__locked = False

                    self.__owner.thread = None
                    self.__owner.description = None

                    self.__main_lock.release()

    @staticmethod
    def critical_section(
        decorated_function: typing.Callable[..., typing.Any]
    ) -> typing.Callable[..., typing.Any]:
        """ Decorate a method with a lock protection (class methods and static methods are unsupported)
        """

        if not inspect.isfunction(decorated_function) or not len(inspect.signature(decorated_function).parameters):
            raise TypeError('The decorated function is not an ordinary method')

        def locked_function(
            original_function: typing.Callable[..., typing.Any],
            self_obj: 'CriticalResource',
            *args: typing.Any,
            **kwargs: typing.Any
        ) -> typing.Any:

            if not isinstance(self_obj, CriticalResource):
                raise TypeError(
                    'Invalid object type. It must be inherited from CriticalResource class and decorated method must'
                    ' be bounded'
                )

            with self_obj.critical_context(self_obj.lock_timeout(), description=repr(decorated_function)):
                return original_function(self_obj, *args, **kwargs)

        result = decorator.decorator(
            locked_function
        )(decorated_function)

        result.__pyknic_lock_free_fn__ = decorated_function  # type: ignore[attr-defined]  # by design

        return result

    def __init__(self, timeout: typing.Union[int, float, None] = None) -> None:
        """ Create a lock

        :param timeout: the same as 'timeout' in the :meth:`.CriticalResource.LockFreeContext.__init__` method
        """
        self.__pre_lock = threading.Lock()
        self.__main_lock = threading.Lock()
        self.__timeout = timeout
        self.__owner = CriticalResource.LockOwner()

    def lock_timeout(self) -> typing.Union[int, float, None]:
        """ Return a timeout that will be used as a default for a lock acquisition
        """
        return self.__timeout

    def critical_context(
        self,
        timeout: typing.Union[int, float, None] = None,
        description: typing.Optional[str] = None
    ) -> 'LockFreeContext':
        """ Create a lock free context for this object

        :param timeout: the same as 'timeout' in the :meth:`.CriticalResource.LockFreeContext.__init__` method
        :param description: the same as 'description' in the :meth:`.CriticalResource.LockFreeContext.__init__` method
        """
        return CriticalResource.LockFreeContext(
            self, self.__owner, self.__main_lock, self.__pre_lock, timeout=timeout, description=description
        )
