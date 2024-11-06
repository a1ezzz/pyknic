# -*- coding: utf-8 -*-

import threading
import time

import pytest

from datetime import datetime, timezone

from pyknic.lib.tasks.plain_task import PlainTask
from pyknic.lib.tasks.proto import TaskProto, ScheduledTaskPostponePolicy
from pyknic.lib.tasks.threaded_task import ThreadedTask
from pyknic.lib.tasks.scheduler.record import ScheduleRecord
from pyknic.lib.signals.proxy import QueueCallbackException

from pyknic.lib.tasks.scheduler.scheduler_executor import SchedulerExecutor


class TestSchedulerExecutor:

    class Task(TaskProto):

        def __init__(
            self,
            callback_registry: 'CallbackRegistry',  # type: ignore[name-defined]  # noqa: F821  # conftest issue
            callback_id: str
        ):
            TaskProto.__init__(self)
            self.event = threading.Event()
            self.__callback_registry = callback_registry
            self.__callback_id = callback_id

        def start(self) -> None:
            self.event.wait()
            self.__callback_registry.callback(self.__callback_id)()

    def test_plain(
        self,
        callbacks_registry: 'CallbackRegistry'  # type: ignore[name-defined]  # noqa: F821  # conftest issue
    ) -> None:
        executor = SchedulerExecutor()
        threaded_queue = ThreadedTask(executor.queue_proxy())
        record = ScheduleRecord(PlainTask(callbacks_registry.callback('test-callback')))

        threaded_queue.start()
        executor.submit(record)

        executor.await_tasks()
        threaded_queue.stop()
        threaded_queue.join()

        assert(callbacks_registry.calls('test-callback') == 1)

    def test_scheduler_limits(
        self,
        callbacks_registry: 'CallbackRegistry'  # type: ignore[name-defined]  # noqa: F821  # conftest issue
    ) -> None:

        executor = SchedulerExecutor(2)
        threaded_queue = ThreadedTask(executor.queue_proxy())
        record1 = ScheduleRecord(TestSchedulerExecutor.Task(callbacks_registry, 'test-callback'))
        record2 = ScheduleRecord(TestSchedulerExecutor.Task(callbacks_registry, 'test-callback'))
        record3 = ScheduleRecord(TestSchedulerExecutor.Task(callbacks_registry, 'test-callback'))
        record4 = ScheduleRecord(TestSchedulerExecutor.Task(callbacks_registry, 'test-callback'))

        threaded_queue.start()

        time.sleep(1)

        executor.submit(record1)
        executor.submit(record2)
        executor.submit(record3)
        executor.submit(record4)

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

    def test_outdated_ttl(
        self,
        callbacks_registry: 'CallbackRegistry',  # type: ignore[name-defined]  # noqa: F821  # conftest issue
        signals_registry: 'SignalsRegistry'  # type: ignore[name-defined]  # noqa: F821  # conftest issue
    ) -> None:
        executor = SchedulerExecutor(1)
        threaded_queue = ThreadedTask(executor.queue_proxy())
        executor.callback(SchedulerExecutor.scheduled_task_expired, signals_registry)
        threaded_queue.start()

        old_record = ScheduleRecord(
            TestSchedulerExecutor.Task(callbacks_registry, 'test-callback'),
            ttl=1
        )

        executor.submit(old_record)

        assert(signals_registry.dump(True) == [
            (executor, SchedulerExecutor.scheduled_task_expired, old_record),
        ])

        executor.await_tasks()
        threaded_queue.stop()
        threaded_queue.join()

    def test_expired_ttl(
        self,
        callbacks_registry: 'CallbackRegistry',  # type: ignore[name-defined]  # noqa: F821  # conftest issue
        signals_registry: 'SignalsRegistry'  # type: ignore[name-defined]  # noqa: F821  # conftest issue
    ) -> None:
        executor = SchedulerExecutor(1)
        threaded_queue = ThreadedTask(executor.queue_proxy())
        executor.callback(SchedulerExecutor.scheduled_task_expired, signals_registry)
        threaded_queue.start()

        long_run_record = ScheduleRecord(TestSchedulerExecutor.Task(callbacks_registry, 'test-callback'))
        executor.submit(long_run_record)

        outdated_record = ScheduleRecord(
            TestSchedulerExecutor.Task(callbacks_registry, 'test-callback'),
            ttl=(datetime.now(timezone.utc).timestamp() + 3)
        )
        executor.submit(outdated_record)

        assert(signals_registry.dump(True) == [])
        time.sleep(5)
        long_run_record.task().event.set()  # type: ignore[attr-defined]  # test simplification

        executor.await_tasks()
        threaded_queue.stop()
        threaded_queue.join()

        assert(signals_registry.dump(True) == [
            (executor, SchedulerExecutor.scheduled_task_expired, outdated_record),
        ])

    def test_group_id_postpone(
        self,
        callbacks_registry: 'CallbackRegistry',  # type: ignore[name-defined]  # noqa: F821  # conftest issue
        signals_registry: 'SignalsRegistry'  # type: ignore[name-defined]  # noqa: F821  # conftest issue
    ) -> None:
        executor = SchedulerExecutor(2)
        threaded_queue = ThreadedTask(executor.queue_proxy())
        executor.callback(SchedulerExecutor.scheduled_task_postponed, signals_registry)
        threaded_queue.start()

        first_record = ScheduleRecord(
            TestSchedulerExecutor.Task(callbacks_registry, 'test-callback'),
            group_id='test-group'
        )
        executor.submit(first_record)

        assert(signals_registry.dump(True) == [])

        second_record = ScheduleRecord(
            TestSchedulerExecutor.Task(callbacks_registry, 'test-callback'),
            group_id='test-group',
            simultaneous_runs=1
        )
        executor.submit(second_record)

        assert(signals_registry.dump(True) == [
            (executor, SchedulerExecutor.scheduled_task_postponed, second_record)
        ])

        first_record.task().event.set()  # type: ignore[attr-defined]  # test simplification
        second_record.task().event.set()  # type: ignore[attr-defined]  # test simplification

        executor.await_tasks()
        threaded_queue.stop()
        threaded_queue.join()

        assert(signals_registry.dump(True) == [])

    def test_postpone(
        self,
        callbacks_registry: 'CallbackRegistry',  # type: ignore[name-defined]  # noqa: F821  # conftest issue
        signals_registry: 'SignalsRegistry'  # type: ignore[name-defined]  # noqa: F821  # conftest issue
    ) -> None:
        executor = SchedulerExecutor(1)
        threaded_queue = ThreadedTask(executor.queue_proxy())
        executor.callback(SchedulerExecutor.scheduled_task_postponed, signals_registry)
        threaded_queue.start()

        first_record = ScheduleRecord(TestSchedulerExecutor.Task(callbacks_registry, 'test-callback'))
        executor.submit(first_record)

        assert(signals_registry.dump(True) == [])

        second_record = ScheduleRecord(TestSchedulerExecutor.Task(callbacks_registry, 'test-callback'))
        executor.submit(second_record)

        assert(signals_registry.dump(True) == [
            (executor, SchedulerExecutor.scheduled_task_postponed, second_record)
        ])

        first_record.task().event.set()  # type: ignore[attr-defined]  # test simplification
        second_record.task().event.set()  # type: ignore[attr-defined]  # test simplification

        executor.await_tasks()
        threaded_queue.stop()
        threaded_queue.join()

        assert(signals_registry.dump(True) == [])

    def test_complete_signal(
        self,
        callbacks_registry: 'CallbackRegistry',  # type: ignore[name-defined]  # noqa: F821  # conftest issue
        signals_registry: 'SignalsRegistry'  # type: ignore[name-defined]  # noqa: F821  # conftest issue
    ) -> None:
        executor = SchedulerExecutor()
        threaded_queue = ThreadedTask(executor.queue_proxy())
        executor.callback(SchedulerExecutor.scheduled_task_completed, signals_registry)
        threaded_queue.start()

        record = ScheduleRecord(TestSchedulerExecutor.Task(callbacks_registry, 'test-callback'))
        executor.submit(record)

        assert(signals_registry.dump(True) == [])

        record.task().event.set()  # type: ignore[attr-defined]  # test simplification

        executor.await_tasks()
        threaded_queue.stop()
        threaded_queue.join()

        assert(signals_registry.dump(True) == [
            (executor, SchedulerExecutor.scheduled_task_completed, record),
        ])

    def test_dropped(
        self,
        callbacks_registry: 'CallbackRegistry',  # type: ignore[name-defined]  # noqa: F821  # conftest issue
        signals_registry: 'SignalsRegistry'  # type: ignore[name-defined]  # noqa: F821  # conftest issue
    ) -> None:
        executor = SchedulerExecutor(1)
        threaded_queue = ThreadedTask(executor.queue_proxy())
        executor.callback(SchedulerExecutor.scheduled_task_dropped, signals_registry)
        threaded_queue.start()

        first_record = ScheduleRecord(TestSchedulerExecutor.Task(callbacks_registry, 'test-callback'))
        executor.submit(first_record)

        assert(signals_registry.dump(True) == [])

        second_record = ScheduleRecord(
            TestSchedulerExecutor.Task(callbacks_registry, 'test-callback'),
            postpone_policy=ScheduledTaskPostponePolicy.drop
        )
        executor.submit(second_record)

        assert(signals_registry.dump(True) == [
            (executor, SchedulerExecutor.scheduled_task_dropped, second_record)
        ])

        first_record.task().event.set()  # type: ignore[attr-defined]  # test simplification
        second_record.task().event.set()  # type: ignore[attr-defined]  # test simplification

        executor.await_tasks()
        threaded_queue.stop()
        threaded_queue.join()

        assert(signals_registry.dump(True) == [])

    def test_keep_first_signal(
        self,
        callbacks_registry: 'CallbackRegistry',  # type: ignore[name-defined]  # noqa: F821  # conftest issue
        signals_registry: 'SignalsRegistry'  # type: ignore[name-defined]  # noqa: F821  # conftest issue
    ) -> None:
        executor = SchedulerExecutor(1)
        threaded_queue = ThreadedTask(executor.queue_proxy())
        executor.callback(SchedulerExecutor.scheduled_task_dropped, signals_registry)
        threaded_queue.start()

        first_record = ScheduleRecord(TestSchedulerExecutor.Task(callbacks_registry, 'test-callback'))
        executor.submit(first_record)

        assert(signals_registry.dump(True) == [])

        second_record = ScheduleRecord(
            TestSchedulerExecutor.Task(callbacks_registry, 'test-callback'),
            group_id='test-group1'
        )
        executor.submit(second_record)

        third_record = ScheduleRecord(
            TestSchedulerExecutor.Task(callbacks_registry, 'test-callback'),
            postpone_policy=ScheduledTaskPostponePolicy.keep_first,
            group_id='test-group1'
        )
        executor.submit(third_record)

        for _ in range(100):
            test_result = (signals_registry.dump(True) == [
                (executor, SchedulerExecutor.scheduled_task_dropped, third_record)
            ])

            if test_result:
                break
            time.sleep(0.1)
        else:
            assert(0)

        first_record.task().event.set()  # type: ignore[attr-defined]  # test simplification
        second_record.task().event.set()  # type: ignore[attr-defined]  # test simplification

        executor.await_tasks()
        threaded_queue.stop()
        threaded_queue.join()

        assert(signals_registry.dump(True) == [])

    def test_cancel_postponed(
        self,
        callbacks_registry: 'CallbackRegistry',  # type: ignore[name-defined]  # noqa: F821  # conftest issue
        signals_registry: 'SignalsRegistry'  # type: ignore[name-defined]  # noqa: F821  # conftest issue
    ) -> None:
        executor = SchedulerExecutor(1)
        threaded_queue = ThreadedTask(executor.queue_proxy())
        executor.callback(SchedulerExecutor.scheduled_task_dropped, signals_registry)
        threaded_queue.start()

        first_record = ScheduleRecord(TestSchedulerExecutor.Task(callbacks_registry, 'test-callback'))
        executor.submit(first_record)

        assert(signals_registry.dump(True) == [])

        second_record = ScheduleRecord(
            TestSchedulerExecutor.Task(callbacks_registry, 'test-callback'),
        )
        executor.submit(second_record)
        executor.cancel_postponed_tasks()

        for _ in range(100):
            test_result = (signals_registry.dump(True) == [
                (executor, SchedulerExecutor.scheduled_task_dropped, second_record)
            ])

            if test_result:
                break
            time.sleep(0.1)
        else:
            assert(0)

        first_record.task().event.set()  # type: ignore[attr-defined]  # test simplification

        executor.await_tasks()
        threaded_queue.stop()
        threaded_queue.join()

        assert(signals_registry.dump(True) == [])

    def test_exception(
        self,
        callbacks_registry: 'CallbackRegistry',  # type: ignore[name-defined]  # noqa: F821  # conftest issue
    ) -> None:
        executor = SchedulerExecutor()
        threaded_queue = ThreadedTask(executor.queue_proxy())
        threaded_queue.start()

        task = TestSchedulerExecutor.Task(callbacks_registry, 'test-callback')
        first_record = ScheduleRecord(task)
        executor.submit(first_record)

        second_record = ScheduleRecord(task)
        with pytest.raises(QueueCallbackException):
            executor.submit(second_record)

        first_record.task().event.set()  # type: ignore[attr-defined]  # test simplification

        executor.await_tasks()
        threaded_queue.stop()
        threaded_queue.join()
