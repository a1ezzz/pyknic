# -*- coding: utf-8 -*-

import time
import threading
import pytest

from pyknic.lib.tasks.thread_executor import ThreadExecutor, ThreadedTaskCompleted
from pyknic.lib.tasks.proto import TaskExecutorProto, TaskProto, NoSuchTaskError, TaskResult


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

        def terminate(self) -> None:
            self.__stop_event.set()

    def test(self) -> None:
        executor = ThreadExecutor()
        assert(isinstance(executor, TaskExecutorProto) is True)

        assert(set(executor.tasks()) == set())
        assert(len(executor) == 0)

    def test_exceptions(self) -> None:
        executor = ThreadExecutor()

        with pytest.raises(NoSuchTaskError):
            executor.join_task(TestThreadExecutor.Task())

        with pytest.raises(NoSuchTaskError):
            executor.stop_task(TestThreadExecutor.Task())

        with pytest.raises(NoSuchTaskError):
            executor.terminate_task(TestThreadExecutor.Task())

    def test_join(self) -> None:
        task = TestThreadExecutor.Task()
        executor = ThreadExecutor()
        assert(executor.submit_task(task) is True)
        executor.stop_task(task)

        while not executor.join_task(task):
            time.sleep(0.1)

    def test_awaited_join(self) -> None:
        task = TestThreadExecutor.Task()
        executor = ThreadExecutor()
        assert(executor.submit_task(task) is True)
        executor.stop_task(task)

        def thread_fn() -> None:
            time.sleep(0.5)
            task.stop()

        thread = threading.Thread(target=thread_fn)
        thread.start()

        executor.join_task(task, await_task=True)
        thread.join()

    def test_threads_number(self) -> None:
        task1 = TestThreadExecutor.Task()
        task2 = TestThreadExecutor.Task()
        task3 = TestThreadExecutor.Task()

        executor = ThreadExecutor(2)
        assert(executor.submit_task(task1) is True)
        assert(len(executor) == 1)
        assert(set(executor.tasks()) == {task1})

        assert(executor.submit_task(task1) is False)

        assert(len(executor) == 1)
        assert(executor.submit_task(task2) is True)
        assert(len(executor) == 2)
        assert(set(executor.tasks()) == {task1, task2})

        assert(executor.submit_task(task3) is False)
        assert(len(executor) == 2)
        assert(set(executor.tasks()) == {task1, task2})

        executor.terminate_task(task1)
        executor.terminate_task(task2)

        while not executor.join_threads():
            time.sleep(0.1)

        assert(len(executor) == 0)
        assert(set(executor.tasks()) == set())

    def test_signals(
        self,
        signals_registry: 'SignalsRegistry',  # type: ignore[name-defined]  # noqa: F821  # conftest issue
    ) -> None:
        task = TestThreadExecutor.Task()

        executor = ThreadExecutor()
        executor.callback(ThreadExecutor.task_completed, signals_registry)
        executor.submit_task(task)

        task.stop()

        while not executor.join_threads():
            time.sleep(0.1)

        assert(
            signals_registry.dump(True) == [(
                executor,
                ThreadExecutor.task_completed,
                ThreadedTaskCompleted(task, TaskResult(None, exception=None))
            )]
        )

    def test_context(self) -> None:
        task1 = TestThreadExecutor.Task()
        task2 = TestThreadExecutor.Task()

        executor = ThreadExecutor(2)
        with executor.executor_context():
            with executor.executor_context():
                with pytest.raises(ValueError):
                    with executor.executor_context():
                        pass

        with executor.executor_context() as c:
            c.submit_task(task1)
            assert(set(executor.tasks()) == {task1})

            with pytest.raises(ValueError):
                c.submit_task(task2)

        task1.stop()
        while not executor.join_threads():
            time.sleep(0.1)
