# -*- coding: utf-8 -*-

import time
import threading
import pytest

from pyknic.lib.tasks.thread_executor import ThreadExecutor, NoFreeSlotError
from pyknic.lib.tasks.proto import TaskExecutorProto, TaskProto, NoSuchTaskError, TaskStartError


def test_exceptions() -> None:
    assert(issubclass(NoFreeSlotError, Exception) is True)


class TestThreadExecutor:

    class Task(TaskProto):

        def __init__(self) -> None:
            TaskProto.__init__(self)
            self.__stop_event = threading.Event()

        def start(self) -> None:
            self.__stop_event.clear()
            self.__stop_event.wait()

        def stop(self) -> None:
            self.__stop_event.set()

    def test(self) -> None:
        executor = ThreadExecutor()
        assert(isinstance(executor, TaskExecutorProto) is True)

        assert(set(executor.tasks()) == set())

    def test_exceptions(self) -> None:
        executor = ThreadExecutor()

        with pytest.raises(NoSuchTaskError):
            executor.complete_task(TestThreadExecutor.Task())

        with pytest.raises(NoSuchTaskError):
            executor.wait_task(TestThreadExecutor.Task())

    def test_join(self) -> None:
        task = TestThreadExecutor.Task()
        executor = ThreadExecutor()
        assert(executor.submit_task(task) is True)
        task.stop()

        while not executor.complete_task(task):
            time.sleep(0.1)

    def test_awaited_join(self) -> None:

        task = TestThreadExecutor.Task()
        executor = ThreadExecutor()
        assert(executor.submit_task(task) is True)

        def thread_fn() -> None:
            nonlocal task
            time.sleep(0.5)
            task.stop()

        thread = threading.Thread(target=thread_fn)
        thread.start()

        executor.wait_task(task)
        executor.complete_task(task)

        thread.join()

    def test_threads_number(self) -> None:
        task1 = TestThreadExecutor.Task()
        task2 = TestThreadExecutor.Task()
        task3 = TestThreadExecutor.Task()

        executor = ThreadExecutor(2)
        assert(executor.submit_task(task1) is True)
        assert(set(executor.tasks()) == {task1})

        assert(executor.submit_task(task1) is False)

        assert(executor.submit_task(task2) is True)
        assert(set(executor.tasks()) == {task1, task2})

        assert(executor.submit_task(task3) is False)

        assert(set(executor.tasks()) == {task1, task2})

        task1.stop()
        task2.stop()

        executor.wait_task(task1)
        executor.wait_task(task2)
        executor.complete_task(task1)
        executor.complete_task(task2)

        assert(set(executor.tasks()) == set())

    def test_context(self) -> None:
        task1 = TestThreadExecutor.Task()
        task2 = TestThreadExecutor.Task()

        executor = ThreadExecutor(2)
        with executor.executor_context():
            with executor.executor_context():
                with pytest.raises(NoFreeSlotError):
                    with executor.executor_context():
                        pass

        with executor.executor_context() as c:
            c.submit_task(task1)
            assert(set(executor.tasks()) == {task1})

            with pytest.raises(TaskStartError):
                c.submit_task(task2)

        task1.stop()
        executor.wait_task(task1)
        executor.complete_task(task1)
