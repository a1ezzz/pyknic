# -*- coding: utf-8 -*-

import gc
import functools
import pytest
import threading
import typing

from pyknic.lib.thread import acquire_lock, critical_section_dynamic_lock, critical_section_lock, CriticalResource
from pyknic.lib.thread import CriticalSectionError


def test_acquire_lock() -> None:

    lock = threading.Lock()
    assert(acquire_lock(lock) is True)  # blocking mode - may wait forever
    assert(acquire_lock(lock, timeout=-1) is False)  # lock is already locked and non-blocking mode is used
    assert(acquire_lock(lock, timeout=1) is False)  # lock is already locked and blocking mode is used
    lock.release()
    assert(acquire_lock(lock, timeout=-1) is True)


@pytest.mark.parametrize(
    "threads_num, increments, lock_decorator", [
        (50, 50, functools.partial(critical_section_dynamic_lock, lock_fn=lambda: threading.Lock()), ),
        (50, 50, functools.partial(critical_section_lock, threading.Lock()), )
    ]
)
def test_critical_section(
    threads_num: int, increments: int, lock_decorator: typing.Callable[..., typing.Callable[..., typing.Any]]
) -> None:

    counter = 0

    def shared_counter_fn() -> None:
        nonlocal counter
        for i in range(increments):
            counter += 1

    thread_safe_fn = lock_decorator()(shared_counter_fn)

    threads = [threading.Thread(target=thread_safe_fn) for _ in range(threads_num)]
    for th in threads:
        th.start()

    for th in threads:
        th.join()

    assert(counter == (threads_num * increments))


def test_critical_section_timeout() -> None:
    lock = threading.Lock()
    lock.acquire()

    def fixed_timeout_fn(
        timeout: typing.Union[int, float, None]
    ) -> typing.Callable[..., typing.Union[int, float, None]]:
        def result(*args: typing.Any, **kwargs: typing.Any) -> typing.Union[int, float, None]:
            return timeout
        return result

    thread_dynamic_safe_fn = critical_section_dynamic_lock(lambda: lock, timeout_fn=fixed_timeout_fn(3))(lambda: None)
    with pytest.raises(CriticalSectionError):
        thread_dynamic_safe_fn()

    thread_safe_fn = critical_section_lock(lock, timeout=3)(lambda: None)
    with pytest.raises(CriticalSectionError):
        thread_safe_fn()

    lock.release()
    thread_dynamic_safe_fn()
    thread_safe_fn()


class SharedResourceSample(CriticalResource):

    def __init__(self) -> None:
        CriticalResource.__init__(self, timeout=3)
        self.counter = 0

    @CriticalResource.critical_section
    def increase(self) -> None:
        self.counter += 1


class TestCriticalResource:

    @pytest.mark.parametrize("threads_num, repeats", [(50, 50)])
    def test(self, threads_num: int, repeats: int) -> None:
        sr = SharedResourceSample()
        assert(sr.counter == 0)

        def thread_fn_increase() -> None:
            for _ in range(repeats):
                sr.increase()

        threads = [threading.Thread(target=thread_fn_increase) for _ in range(threads_num)]
        for th in threads:
            th.start()

        for th in threads:
            th.join()

        assert(sr.counter == (threads_num * repeats))

    def test_exceptions(self) -> None:
        class A:
            @CriticalResource.critical_section
            def foo(self) -> None:
                pass
        with pytest.raises(TypeError):
            A().foo()


class TestLockFreeContext:

    @pytest.mark.parametrize("threads_num, repeats", [(50, 50)])
    def test(self, threads_num: int, repeats: int) -> None:
        sr = SharedResourceSample()
        assert(sr.counter == 0)

        def thread_fn_increase() -> None:
            for i in range(repeats):
                with sr.critical_context(timeout=1) as c1:
                    c1.increase()

        threads = [threading.Thread(target=thread_fn_increase) for x in range(threads_num)]
        for th in threads:
            th.start()

        for th in threads:
            th.join()

        assert(sr.counter == (threads_num * repeats))

        class A(CriticalResource):
            @classmethod
            def foo(cls, i: int) -> int:
                return 2 * i

        a = A()
        with a.critical_context() as c2:
            assert(c2.foo(1) == 2)  # access to original attributes works still

    def test_exceptions(self) -> None:
        sr = SharedResourceSample()
        c1 = sr.critical_context(timeout=1)

        with c1:
            pass  # this is ok
        with pytest.raises(CriticalSectionError):
            with c1:
                with c1:  # there is no way to lock a context twice
                    pass

        c2 = sr.critical_context(timeout=1)
        with c1:
            pass  # this is fine still
        with pytest.raises(CriticalSectionError):
            with c1:
                with c2:  # there is no way to get in a critical section even from different contexts
                    pass

        with c1:
            pass  # this doesn't do anything bad

        with pytest.raises(CriticalSectionError):
            with c1:
                sr.increase()  # this won't work either

        c1.__enter__()  # the object is "locked"
        with pytest.raises(CriticalSectionError):
            sr.increase()  # the object is locked definitely
        del c1
        gc.collect()
        sr.increase()  # the object was unlocked automatically

        with pytest.raises(CriticalSectionError):
            _ = c2.increase  # access to underlined methods are not allowed without a lock
