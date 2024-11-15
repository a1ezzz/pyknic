# -*- coding: utf-8 -*-

import threading
import time
import typing

import pytest

if typing.TYPE_CHECKING:
    # noinspection PyUnresolvedReferences
    from conftest import SampleTasks, CallbackRegistry, SignalsRegistry, SignalWatcher

from datetime import datetime, timezone

from pyknic.lib.tasks.plain_task import PlainTask
from pyknic.lib.tasks.proto import TaskProto, ScheduledTaskPostponePolicy
from pyknic.lib.tasks.threaded_task import ThreadedTask
from pyknic.lib.tasks.scheduler.record import ScheduleRecord

from pyknic.lib.tasks.scheduler.scheduler_executor import SchedulerExecutor


class TestSchedulerExecutor:

    class Task(TaskProto):

        def __init__(
            self,
            callback_registry: 'CallbackRegistry',
            callback_id: str
        ):
            TaskProto.__init__(self)
            self.event = threading.Event()
            self.__callback_registry = callback_registry
            self.__callback_id = callback_id

        def start(self) -> None:
            self.event.wait()
            self.__callback_registry.callback(self.__callback_id)()

    def test_plain(self, callbacks_registry: 'CallbackRegistry') -> None:
        executor = SchedulerExecutor()
        threaded_queue = ThreadedTask(executor.queue_proxy())
        record = ScheduleRecord(PlainTask(callbacks_registry.callback('test-callback')))

        threaded_queue.start()
        executor.submit(record, blocking=True)

        executor.await_tasks()
        threaded_queue.stop()
        threaded_queue.join()

        assert(callbacks_registry.calls('test-callback') == 1)

    def test_scheduler_limits(self, callbacks_registry: 'CallbackRegistry') -> None:

        executor = SchedulerExecutor(2)
        threaded_queue = ThreadedTask(executor.queue_proxy())
        record1 = ScheduleRecord(TestSchedulerExecutor.Task(callbacks_registry, 'test-callback'))
        record2 = ScheduleRecord(TestSchedulerExecutor.Task(callbacks_registry, 'test-callback'))
        record3 = ScheduleRecord(TestSchedulerExecutor.Task(callbacks_registry, 'test-callback'))
        record4 = ScheduleRecord(TestSchedulerExecutor.Task(callbacks_registry, 'test-callback'))

        threaded_queue.start()

        time.sleep(1)

        executor.submit(record1, blocking=True)
        executor.submit(record2, blocking=True)
        executor.submit(record3, blocking=True)
        executor.submit(record4, blocking=True)

        record1.task().event.set()  # type: ignore[attr-defined]  # test simplification
        record2.task().event.set()  # type: ignore[attr-defined]  # test simplification
        record3.task().event.set()  # type: ignore[attr-defined]  # test simplification
        record4.task().event.set()  # type: ignore[attr-defined]  # test simplification

        for _ in range(100):
            if callbacks_registry.calls('test-callback') == 4:
                break
            time.sleep(0.1)
        else:
            assert(0)

        executor.await_tasks()
        threaded_queue.stop()
        threaded_queue.join()

    def test_outdated_ttl(self, signals_registry: 'SignalsRegistry', sample_tasks: 'SampleTasks') -> None:
        executor = SchedulerExecutor(1)
        threaded_queue = ThreadedTask(executor.queue_proxy())
        executor.callback(SchedulerExecutor.scheduled_task_expired, signals_registry)
        threaded_queue.start()

        old_record = ScheduleRecord(sample_tasks.LongRunningTask(), ttl=1)
        executor.submit(old_record, blocking=True)

        assert(signals_registry.dump(True) == [
            (executor, SchedulerExecutor.scheduled_task_expired, old_record),
        ])

        executor.await_tasks()
        threaded_queue.stop()
        threaded_queue.join()

    def test_expired_ttl(self, signals_registry: 'SignalsRegistry', sample_tasks: 'SampleTasks') -> None:
        executor = SchedulerExecutor(1)
        threaded_queue = ThreadedTask(executor.queue_proxy())
        executor.callback(SchedulerExecutor.scheduled_task_expired, signals_registry)
        threaded_queue.start()

        long_run_record = ScheduleRecord(sample_tasks.LongRunningTask())
        executor.submit(long_run_record, blocking=True)

        outdated_record = ScheduleRecord(
            sample_tasks.LongRunningTask(), ttl=(datetime.now(timezone.utc).timestamp() + 3)
        )
        executor.submit(outdated_record, blocking=True)

        assert(signals_registry.dump(True) == [])
        time.sleep(5)

        executor.stop_running_tasks()
        executor.await_tasks()
        threaded_queue.stop()
        threaded_queue.join()

        assert(signals_registry.dump(True) == [
            (executor, SchedulerExecutor.scheduled_task_expired, outdated_record),
        ])

    def test_group_id_postpone(self, signals_registry: 'SignalsRegistry', sample_tasks: 'SampleTasks') -> None:
        executor = SchedulerExecutor(2)
        threaded_queue = ThreadedTask(executor.queue_proxy())
        executor.callback(SchedulerExecutor.scheduled_task_postponed, signals_registry)
        threaded_queue.start()

        first_record = ScheduleRecord(sample_tasks.LongRunningTask(), group_id='test-group')
        executor.submit(first_record, blocking=True)

        assert(signals_registry.dump(True) == [])

        second_record = ScheduleRecord(sample_tasks.LongRunningTask(), group_id='test-group', simultaneous_runs=1)
        executor.submit(second_record, blocking=True)

        assert(signals_registry.dump(True) == [
            (executor, SchedulerExecutor.scheduled_task_postponed, second_record)
        ])

        executor.cancel_postponed_tasks()
        executor.stop_running_tasks()
        executor.await_tasks()
        threaded_queue.stop()
        threaded_queue.join()

        assert(signals_registry.dump(True) == [])

    def test_postpone(self, signals_registry: 'SignalsRegistry', sample_tasks: 'SampleTasks') -> None:
        executor = SchedulerExecutor(1)
        threaded_queue = ThreadedTask(executor.queue_proxy())
        executor.callback(SchedulerExecutor.scheduled_task_postponed, signals_registry)
        threaded_queue.start()

        first_record = ScheduleRecord(sample_tasks.LongRunningTask())
        executor.submit(first_record, blocking=True)

        assert(signals_registry.dump(True) == [])

        second_record = ScheduleRecord(sample_tasks.LongRunningTask())
        executor.submit(second_record, blocking=True)

        assert(signals_registry.dump(True) == [
            (executor, SchedulerExecutor.scheduled_task_postponed, second_record)
        ])

        executor.cancel_postponed_tasks()
        executor.stop_running_tasks()
        executor.await_tasks()
        threaded_queue.stop()
        threaded_queue.join()

        assert(signals_registry.dump(True) == [])

    def test_complete_signal(self, signals_registry: 'SignalsRegistry', sample_tasks: 'SampleTasks') -> None:
        executor = SchedulerExecutor()
        threaded_queue = ThreadedTask(executor.queue_proxy())
        executor.callback(SchedulerExecutor.scheduled_task_completed, signals_registry)
        threaded_queue.start()

        record = ScheduleRecord(sample_tasks.LongRunningTask())
        executor.submit(record, blocking=True)

        assert(signals_registry.dump(True) == [])

        executor.stop_running_tasks()
        executor.await_tasks()
        threaded_queue.stop()
        threaded_queue.join()

        assert(signals_registry.dump(True) == [
            (executor, SchedulerExecutor.scheduled_task_completed, record),
        ])

    def test_dropped(
        self, signals_registry: 'SignalsRegistry', sample_tasks: 'SampleTasks'
    ) -> None:
        executor = SchedulerExecutor(1)
        threaded_queue = ThreadedTask(executor.queue_proxy())
        executor.callback(SchedulerExecutor.scheduled_task_dropped, signals_registry)
        threaded_queue.start()

        first_record = ScheduleRecord(sample_tasks.LongRunningTask())
        executor.submit(first_record, blocking=True)

        assert(signals_registry.dump(True) == [])

        second_record = ScheduleRecord(sample_tasks.LongRunningTask(), postpone_policy=ScheduledTaskPostponePolicy.drop)
        executor.submit(second_record, blocking=True)

        assert(signals_registry.dump(True) == [
            (executor, SchedulerExecutor.scheduled_task_dropped, second_record)
        ])

        executor.stop_running_tasks()
        executor.await_tasks()
        threaded_queue.stop()
        threaded_queue.join()

        assert(signals_registry.dump(True) == [])

    def test_keep_first_signal(self, signal_watcher: 'SignalWatcher', sample_tasks: 'SampleTasks') -> None:
        executor = SchedulerExecutor(1)
        threaded_queue = ThreadedTask(executor.queue_proxy())
        executor.callback(SchedulerExecutor.scheduled_task_dropped, signal_watcher)
        threaded_queue.start()

        first_record = ScheduleRecord(sample_tasks.LongRunningTask())
        executor.submit(first_record, blocking=True)

        second_record = ScheduleRecord(sample_tasks.LongRunningTask(), group_id='test-group1')
        executor.submit(second_record, blocking=True)

        third_record = ScheduleRecord(
            sample_tasks.LongRunningTask(),
            postpone_policy=ScheduledTaskPostponePolicy.keep_first,
            group_id='test-group1'
        )
        executor.submit(third_record, blocking=True)

        signal_watcher.wait(100)

        executor.cancel_postponed_tasks()
        executor.stop_running_tasks()
        executor.await_tasks()
        threaded_queue.stop()
        threaded_queue.join()

    def test_exception(self, sample_tasks: 'SampleTasks') -> None:
        executor = SchedulerExecutor()
        threaded_queue = ThreadedTask(executor.queue_proxy())
        threaded_queue.start()

        task = sample_tasks.LongRunningTask()
        first_record = ScheduleRecord(task)
        executor.submit(first_record, blocking=True)

        second_record = ScheduleRecord(task)
        with pytest.raises(ValueError):
            executor.submit(second_record, blocking=True)

        executor.stop_running_tasks()
        executor.await_tasks()
        threaded_queue.stop()
        threaded_queue.join()

    @pytest.mark.parametrize(
        "task_args", [
            {"stop_method": True, "terminate_method": False},
            {"stop_method": False, "terminate_method": True}
        ]
    )
    def test_stop_running_tasks(self, sample_tasks: 'SampleTasks', task_args: typing.Dict[str, bool]) -> None:
        executor = SchedulerExecutor(1)
        threaded_queue = ThreadedTask(executor.queue_proxy())
        threaded_queue.start()

        first_task = sample_tasks.LongRunningTask(**task_args)
        executor.submit(ScheduleRecord(first_task), blocking=True)

        second_task = sample_tasks.LongRunningTask(**task_args)
        executor.submit(ScheduleRecord(second_task), blocking=True)

        assert(executor.running_tasks() == (first_task, ))
        assert(executor.pending_tasks() == (second_task, ))

        executor.cancel_postponed_tasks()
        executor.stop_running_tasks()
        executor.await_tasks()
        threaded_queue.stop()
        threaded_queue.join()

    def test_await_exception(self, sample_tasks: 'SampleTasks') -> None:
        executor = SchedulerExecutor()
        threaded_queue = ThreadedTask(executor.queue_proxy())
        threaded_queue.start()

        record = ScheduleRecord(sample_tasks.LongRunningTask())
        executor.submit(record, blocking=True)

        import time
        time.sleep(1)

        with pytest.raises(TimeoutError):
            executor.await_tasks(1)

        executor.stop_running_tasks()
        executor.await_tasks()
        threaded_queue.stop()
        threaded_queue.join()

    def test_corrupted_task(self, sample_tasks: 'SampleTasks') -> None:

        class Task(TaskProto):
            def start(self) -> None:
                raise ValueError('!')

        executor = SchedulerExecutor()

        threaded_queue = ThreadedTask(executor.queue_proxy())
        threaded_queue.start()

        task = Task()
        record = ScheduleRecord(task)
        executor.submit(record, blocking=True)

        executor.stop_running_tasks()
        executor.await_tasks()
        threaded_queue.stop()
        threaded_queue.join()
