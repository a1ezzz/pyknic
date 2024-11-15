# -*- coding: utf-8 -*-

import functools
import pytest
import threading
import time
import typing

if typing.TYPE_CHECKING:
    # noinspection PyUnresolvedReferences
    from conftest import SignalsRegistry, SampleTasks

from pyknic.lib.tasks.plain_task import PlainTask
from pyknic.lib.tasks.proto import TaskProto, TaskResult, TaskStartError
from pyknic.lib.tasks.threaded_task import ThreadedTask


def sample_function(event: threading.Event, start_event: typing.Optional[threading.Event] = None) -> threading.Event:
    if start_event:
        start_event.set()
    event.wait()
    return event


class TestThreadTask:

    def test_plain(self) -> None:
        event = threading.Event()
        task = ThreadedTask.plain_task(functools.partial(sample_function, event))
        task.start()
        event.set()
        task.wait()

    def test_wait_w_timeout(self) -> None:
        event = threading.Event()
        task = ThreadedTask.plain_task(functools.partial(sample_function, event))
        task.start()
        event.set()
        task.wait(100)

    def test_join(self) -> None:
        start_event = threading.Event()
        stop_event = threading.Event()

        task = ThreadedTask.plain_task(functools.partial(sample_function, stop_event, start_event))
        assert(task.join() is True)

        task.start()
        start_event.wait()
        assert(task.join() is False)

        stop_event.set()

        while not task.join():  # this loop is a test itself =)
            time.sleep(0.1)

        assert(task.join() is True)

    def test_start_event(self, signals_registry: 'SignalsRegistry') -> None:
        event = threading.Event()
        task = ThreadedTask.plain_task(functools.partial(sample_function, event))
        task.callback(TaskProto.task_started, signals_registry)

        task.start()
        event.set()
        task.wait()

        assert(signals_registry.dump(True) == [
            (task, TaskProto.task_started, None),
        ])

    def test_complete_event(self, signals_registry: 'SignalsRegistry') -> None:
        plain_task = PlainTask(lambda: None)
        task = ThreadedTask(plain_task)
        task.callback(TaskProto.task_completed, signals_registry)
        task.callback(ThreadedTask.thread_ready, signals_registry)

        task.start()
        task.wait()

        assert(signals_registry.dump(True) == [
            (task, ThreadedTask.thread_ready, plain_task),
            (task, TaskProto.task_completed, TaskResult())
        ])

    def test_stop(self, sample_tasks: 'SampleTasks') -> None:
        task = ThreadedTask(sample_tasks.LongRunningTask(terminate_method=False))
        task.start()
        task.stop()
        task.wait()

    def test_terminate(self, sample_tasks: 'SampleTasks') -> None:
        task = ThreadedTask(sample_tasks.LongRunningTask(stop_method=False))
        task.start()
        task.terminate()
        task.wait()

    def test_start_exception(self) -> None:
        event = threading.Event()
        task = ThreadedTask.plain_task(functools.partial(sample_function, event))
        task.start()

        with pytest.raises(TaskStartError):
            task.start()

        event.set()
        task.wait()

    def test_task_result(self, signals_registry: 'SignalsRegistry') -> None:
        event = threading.Event()
        task = ThreadedTask.plain_task(functools.partial(sample_function, event))
        task.callback(TaskProto.task_completed, signals_registry)

        task.start()
        event.set()
        task.wait()

        assert(signals_registry.dump(True) == [
            (task, TaskProto.task_completed, TaskResult()),
        ])

    def test_task_exception(self, signals_registry: 'SignalsRegistry') -> None:
        class Task(TaskProto):

            def __init__(self, exc: BaseException) -> None:
                TaskProto.__init__(self)
                self.__exc = exc

            def start(self) -> None:
                raise self.__exc

        task_exception = ValueError('!')
        original_task = Task(task_exception)
        task = ThreadedTask(original_task)
        signals_registry.thread_safe()
        task.callback(TaskProto.task_completed, signals_registry)
        task.callback(ThreadedTask.thread_ready, signals_registry)

        task.start()
        task.wait()

        assert(signals_registry.dump(True) == [
            (task, ThreadedTask.thread_ready, original_task),
            (task, TaskProto.task_completed, TaskResult(exception=task_exception)),
        ])
