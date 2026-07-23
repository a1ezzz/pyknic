# -*- coding: utf-8 -*-

import gc
import pytest
import time
import threading

from pyknic.lib.thread import CriticalResource, CriticalSectionError


class SharedResourceSample(CriticalResource):

    def __init__(self) -> None:
        CriticalResource.__init__(self, timeout=3)
        self.counter = 0

    @CriticalResource.critical_section
    def increase(self) -> None:
        previous_value = self.counter
        time.sleep(0.0001)
        next_value = previous_value + 1
        time.sleep(0.0001)
        self.counter = next_value


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
            # the A class is not inherited from the CriticalResource class
            A().foo()

        with pytest.raises(TypeError):
            # static methods are not supported

            class B:

                @CriticalResource.critical_section
                @staticmethod
                def foo() -> None:
                    pass

    def test_self_lock(self) -> None:
        resource = SharedResourceSample()
        with resource.critical_context():

            with pytest.raises(CriticalSectionError):
                with resource.critical_context():
                    pass

            with pytest.raises(CriticalSectionError):
                resource.increase()


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
