# -*- coding: utf-8 -*-

import pytest
import threading
import typing

if typing.TYPE_CHECKING:
    # noinspection PyUnresolvedReferences
    from conftest import CallbackRegistry, SignalWatcher, SampleTasks

from pyknic.lib.tasks.proto import SchedulerProto, TaskStopError, TaskProto, SchedulerFeedback, ScheduleSourceProto
from pyknic.lib.tasks.proto import ScheduledTaskPostponePolicy
from pyknic.lib.tasks.plain_task import PlainTask
from pyknic.lib.tasks.threaded_task import ThreadedTask
from pyknic.lib.tasks.scheduler.plain_sources import InstantTaskSource
from pyknic.lib.tasks.scheduler.scheduler import Scheduler
from pyknic.lib.tasks.scheduler.record import ScheduleRecord
from pyknic.lib.signals.proxy import QueueCallbackException


class TestScheduler:

    class SynCallback:
        # TODO: refactor this

        def __init__(self) -> None:
            self.event = threading.Event()

        def __call__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
            self.event.set()

        @staticmethod
        def flush(source: InstantTaskSource) -> None:
            syn = TestScheduler.SynCallback()
            source.schedule_record(ScheduleRecord(PlainTask(syn)))
            syn.event.wait()

    def test(self, callbacks_registry: 'CallbackRegistry') -> None:
        scheduler = Scheduler()
        source1 = InstantTaskSource()
        source2 = InstantTaskSource()

        threaded_scheduler = ThreadedTask(scheduler)
        threaded_scheduler.start()

        scheduler.subscribe(source1)
        scheduler.subscribe(source2)

        source1.schedule_record(ScheduleRecord(PlainTask(callbacks_registry.callback('test-callback'))))
        TestScheduler.SynCallback.flush(source2)
        assert(callbacks_registry.calls('test-callback') == 1)

        scheduler.unsubscribe(source1)
        source1.schedule_record(ScheduleRecord(PlainTask(callbacks_registry.callback('test-callback'))))
        TestScheduler.SynCallback.flush(source2)
        assert(callbacks_registry.calls('test-callback') == 1)

        threaded_scheduler.stop()
        threaded_scheduler.join()

    def test_exception(self) -> None:
        scheduler = Scheduler()
        source = InstantTaskSource()

        threaded_scheduler = ThreadedTask(scheduler)
        threaded_scheduler.start()

        with pytest.raises(QueueCallbackException):
            scheduler.unsubscribe(source)

        scheduler.subscribe(source)

        with pytest.raises(QueueCallbackException):
            scheduler.subscribe(source)

        threaded_scheduler.stop()
        threaded_scheduler.join()

    def test_stop_exception(self) -> None:

        class UnstoppableTask(TaskProto):

            def __init__(self) -> None:
                TaskProto.__init__(self)
                self.event = threading.Event()

            def start(self) -> None:
                self.event.wait()

        scheduler = Scheduler()
        source = InstantTaskSource()
        task = UnstoppableTask()

        threaded_scheduler = ThreadedTask(scheduler)
        threaded_scheduler.start()

        scheduler.subscribe(source)
        source.schedule_record(ScheduleRecord(task))

        with pytest.raises(TaskStopError):
            threaded_scheduler.stop()

        task.event.set()
        threaded_scheduler.stop()
        threaded_scheduler.join()

    def test_signal_task_scheduled(self, signal_watcher: 'SignalWatcher') -> None:
        scheduler = Scheduler()
        source = InstantTaskSource()
        record = ScheduleRecord(PlainTask(lambda: None))

        scheduler.callback(SchedulerProto.task_scheduled, signal_watcher)

        threaded_scheduler = ThreadedTask(scheduler)
        threaded_scheduler.start()

        scheduler.subscribe(source)
        source.schedule_record(record)

        signal_watcher.wait(10)  # will raise an exception in case of failure

        threaded_scheduler.stop()
        threaded_scheduler.join()

    def test_feedback(self, callbacks_registry: 'CallbackRegistry') -> None:

        class CustomSource(ScheduleSourceProto):

            def scheduler_feedback(self, scheduler: 'SchedulerProto', feedback: SchedulerFeedback) -> None:
                if feedback == SchedulerFeedback.source_subscribed:
                    callbacks_registry.callback('source-subscribed')()
                elif feedback == SchedulerFeedback.source_unsubscribed:
                    callbacks_registry.callback('source-unsubscribed')()

        source = CustomSource()
        scheduler = Scheduler()
        threaded_scheduler = ThreadedTask(scheduler)
        threaded_scheduler.start()
        assert(callbacks_registry.calls("source-subscribed") == 0)
        assert(callbacks_registry.calls("source-unsubscribed") == 0)

        scheduler.subscribe(source)
        assert(callbacks_registry.calls("source-subscribed") == 1)
        assert(callbacks_registry.calls("source-unsubscribed") == 0)

        scheduler.unsubscribe(source)
        assert(callbacks_registry.calls("source-subscribed") == 1)
        assert(callbacks_registry.calls("source-unsubscribed") == 1)

        threaded_scheduler.stop()
        threaded_scheduler.join()

    def test_signal_task_dropped(
        self, signal_watcher: 'SignalWatcher', sample_tasks: 'SampleTasks'
    ) -> None:
        source = InstantTaskSource()
        scheduler = Scheduler(1)
        threaded_scheduler = ThreadedTask(scheduler)

        scheduler.callback(SchedulerProto.scheduled_task_dropped, signal_watcher)
        threaded_scheduler.start()
        scheduler.subscribe(source)

        source.schedule_record(ScheduleRecord(sample_tasks.LongRunningTask(terminate_method=False)))
        source.schedule_record(ScheduleRecord(
            sample_tasks.LongRunningTask(terminate_method=False), postpone_policy=ScheduledTaskPostponePolicy.drop
        ))
        signal_watcher.wait(100)

        threaded_scheduler.stop()
        threaded_scheduler.join()

    def test_signal_task_postponed(self, signal_watcher: 'SignalWatcher', sample_tasks: 'SampleTasks') -> None:
        source = InstantTaskSource()
        scheduler = Scheduler(1)
        threaded_scheduler = ThreadedTask(scheduler)

        scheduler.callback(SchedulerProto.scheduled_task_postponed, signal_watcher)
        threaded_scheduler.start()
        scheduler.subscribe(source)

        source.schedule_record(ScheduleRecord(sample_tasks.LongRunningTask(terminate_method=False)))
        source.schedule_record(ScheduleRecord(sample_tasks.LongRunningTask(terminate_method=False)))
        signal_watcher.wait(100)

        threaded_scheduler.stop()
        threaded_scheduler.join()

    def test_signal_task_expired(self, signal_watcher: 'SignalWatcher', sample_tasks: 'SampleTasks') -> None:
        source = InstantTaskSource()
        scheduler = Scheduler(1)
        threaded_scheduler = ThreadedTask(scheduler)

        scheduler.callback(SchedulerProto.scheduled_task_expired, signal_watcher)
        threaded_scheduler.start()
        scheduler.subscribe(source)

        source.schedule_record(ScheduleRecord(sample_tasks.LongRunningTask(terminate_method=False), ttl=1))
        signal_watcher.wait(100)

        threaded_scheduler.stop()
        threaded_scheduler.join()

    def test_signal_task_started(self, signal_watcher: 'SignalWatcher', sample_tasks: 'SampleTasks') -> None:
        source = InstantTaskSource()
        scheduler = Scheduler(1)
        threaded_scheduler = ThreadedTask(scheduler)

        scheduler.callback(SchedulerProto.scheduled_task_started, signal_watcher)
        threaded_scheduler.start()
        scheduler.subscribe(source)

        source.schedule_record(ScheduleRecord(sample_tasks.LongRunningTask(terminate_method=False)))
        signal_watcher.wait(100)

        threaded_scheduler.stop()
        threaded_scheduler.join()

    def test_signal_task_complete(self, signal_watcher: 'SignalWatcher', sample_tasks: 'SampleTasks') -> None:

        source = InstantTaskSource()
        scheduler = Scheduler(1)
        threaded_scheduler = ThreadedTask(scheduler)

        scheduler.callback(SchedulerProto.scheduled_task_completed, signal_watcher)
        threaded_scheduler.start()
        scheduler.subscribe(source)

        source.schedule_record(ScheduleRecord(sample_tasks.DummyTask()))
        signal_watcher.wait(100)

        threaded_scheduler.stop()
        threaded_scheduler.join()
