# -*- coding: utf-8 -*-

import asyncio
import pytest
import time
import threading
import typing

if typing.TYPE_CHECKING:
    # noinspection PyUnresolvedReferences
    from conftest import SampleTasks

from pyknic.lib.tasks.thread_executor import ThreadExecutor, NoFreeSlotError
from pyknic.lib.tasks.proto import TaskExecutorProto, NoSuchTaskError, TaskStartError

from fixtures.asyncio import pyknic_async_test


def test_exceptions() -> None:
    assert(issubclass(NoFreeSlotError, Exception) is True)


class TestThreadExecutor:

    def test(self) -> None:
        executor = ThreadExecutor()
        assert(isinstance(executor, TaskExecutorProto) is True)

        assert(set(executor.tasks()) == set())

    @pyknic_async_test
    async def test_exceptions(self, sample_tasks: 'SampleTasks', module_event_loop: asyncio.AbstractEventLoop) -> None:
        executor = ThreadExecutor()

        with pytest.raises(NoSuchTaskError):
            executor.complete_task(sample_tasks.LongRunningTask(terminate_method=False))

        with pytest.raises(NoSuchTaskError):
            executor.wait_task(sample_tasks.LongRunningTask(terminate_method=False))

    def test_join(self, sample_tasks: 'SampleTasks') -> None:
        task = sample_tasks.LongRunningTask(terminate_method=False)
        executor = ThreadExecutor()
        assert(executor.submit_task(task) is True)
        task.stop()

        while not executor.complete_task(task):
            time.sleep(0.1)

    @pytest.mark.filterwarnings("ignore")  # the PytestUnhandledThreadExceptionWarning is a part of the test
    def test_awaited_join(self, sample_tasks: 'SampleTasks') -> None:
        task = sample_tasks.DummyTask()
        executor = ThreadExecutor()
        assert(executor.submit_task(task) is True)

        def thread_fn() -> None:
            nonlocal task  # noqa: F824
            time.sleep(0.5)
            task.stop()

        thread = threading.Thread(target=thread_fn)
        thread.start()

        executor.wait_task(task)
        executor.complete_task(task)

        thread.join()

    def test_awaited_w_timeout_join(self, sample_tasks: 'SampleTasks') -> None:
        task = sample_tasks.LongRunningTask(terminate_method=False)
        executor = ThreadExecutor()
        assert (executor.submit_task(task) is True)

        def thread_fn() -> None:
            nonlocal task  # noqa: F824
            time.sleep(0.5)
            task.stop()

        thread = threading.Thread(target=thread_fn)
        thread.start()

        executor.wait_task(task, timeout=100)
        executor.complete_task(task)

        thread.join()

    @pyknic_async_test
    async def test_async_awaited_join(
        self,
        sample_tasks: 'SampleTasks',
        module_event_loop: asyncio.AbstractEventLoop
    ) -> None:
        task = sample_tasks.LongRunningTask(terminate_method=False)
        executor = ThreadExecutor()

        def thread_fn() -> None:
            nonlocal task  # noqa: F824
            time.sleep(0.5)
            task.stop()

        thread = threading.Thread(target=thread_fn)
        thread.start()

        await executor.start_async(task)
        executor.complete_task(task)

        thread.join()

    def test_threads_number(self, sample_tasks: 'SampleTasks') -> None:
        task1 = sample_tasks.LongRunningTask(terminate_method=False)
        task2 = sample_tasks.LongRunningTask(terminate_method=False)
        task3 = sample_tasks.LongRunningTask(terminate_method=False)

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

    def test_context(self, sample_tasks: 'SampleTasks') -> None:
        task1 = sample_tasks.LongRunningTask(terminate_method=False)
        task2 = sample_tasks.LongRunningTask(terminate_method=False)

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
