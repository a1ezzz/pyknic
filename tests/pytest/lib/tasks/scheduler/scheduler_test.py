# -*- coding: utf-8 -*-

import pytest
import threading
import typing

from pyknic.lib.tasks.proto import SchedulerProto, SchedulerFeedback, ScheduleSourceProto, ScheduledTaskPostponePolicy
from pyknic.lib.tasks.plain_task import PlainTask
from pyknic.lib.tasks.threaded_task import ThreadRunner
from pyknic.lib.tasks.scheduler.plain_sources import InstantTaskSource
from pyknic.lib.tasks.scheduler.scheduler import Scheduler
from pyknic.lib.tasks.scheduler.record import ScheduleRecord

from fixtures.callbacks_n_signals import CallbackRegistry, SignalWatcher
from fixtures.tasks import SampleTasks


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
            source.schedule_record(ScheduleRecord(PlainTask(syn), source))
            syn.event.wait()

    def test(self, callbacks_registry: CallbackRegistry) -> None:
        scheduler = Scheduler()

        with pytest.raises(TimeoutError):
            scheduler.wait_initialization(0.001)

        source1 = InstantTaskSource()
        source2 = InstantTaskSource()

        with ThreadRunner.task(scheduler):

            scheduler.subscribe(source1)
            scheduler.subscribe(source2)

            source1.schedule_record(ScheduleRecord(PlainTask(callbacks_registry.callback('test-callback')), source1))
            TestScheduler.SynCallback.flush(source2)
            assert(callbacks_registry.calls('test-callback') == 1)

            scheduler.unsubscribe(source1)
            source1.schedule_record(ScheduleRecord(PlainTask(callbacks_registry.callback('test-callback')), source1))
            TestScheduler.SynCallback.flush(source2)
            assert(callbacks_registry.calls('test-callback') == 1)

    def test_exception(self) -> None:
        scheduler = Scheduler()
        source = InstantTaskSource()

        with ThreadRunner.task(scheduler):

            with pytest.raises(ValueError):
                scheduler.unsubscribe(source)

            scheduler.subscribe(source)

            with pytest.raises(ValueError):
                scheduler.subscribe(source)

    def test_signal_task_scheduled(self, signal_watcher: SignalWatcher) -> None:
        scheduler = Scheduler()
        source = InstantTaskSource()
        record = ScheduleRecord(PlainTask(lambda: None), source)

        scheduler.callback(SchedulerProto.task_scheduled, signal_watcher)

        with ThreadRunner.task(scheduler):
            scheduler.subscribe(source)
            source.schedule_record(record)

            signal_watcher.wait(10)  # will raise an exception in case of failure

    def test_feedback(self, callbacks_registry: CallbackRegistry) -> None:

        class CustomSource(ScheduleSourceProto):

            def scheduler_feedback(self, scheduler: SchedulerProto, feedback: SchedulerFeedback) -> None:
                if feedback == SchedulerFeedback.source_subscribed:
                    callbacks_registry.callback('source-subscribed')()
                elif feedback == SchedulerFeedback.source_unsubscribed:
                    callbacks_registry.callback('source-unsubscribed')()

        source = CustomSource()
        scheduler = Scheduler()

        with ThreadRunner.task(scheduler):
            assert(callbacks_registry.calls("source-subscribed") == 0)
            assert(callbacks_registry.calls("source-unsubscribed") == 0)

            scheduler.subscribe(source)
            assert(callbacks_registry.calls("source-subscribed") == 1)
            assert(callbacks_registry.calls("source-unsubscribed") == 0)

            scheduler.unsubscribe(source)
            assert(callbacks_registry.calls("source-subscribed") == 1)
            assert(callbacks_registry.calls("source-unsubscribed") == 1)

    def test_signal_task_dropped(
        self, signal_watcher: SignalWatcher, sample_tasks: SampleTasks
    ) -> None:
        source = InstantTaskSource()
        scheduler = Scheduler(1)
        scheduler.callback(SchedulerProto.scheduled_task_dropped, signal_watcher)

        with ThreadRunner.task(scheduler):
            scheduler.subscribe(source)

            source.schedule_record(ScheduleRecord(sample_tasks.LongRunningTask(terminate_method=False), source))
            source.schedule_record(ScheduleRecord(
                sample_tasks.LongRunningTask(terminate_method=False),
                source,
                postpone_policy=ScheduledTaskPostponePolicy.drop
            ))
            signal_watcher.wait(100)

    def test_signal_task_postponed(self, signal_watcher: SignalWatcher, sample_tasks: SampleTasks) -> None:
        source = InstantTaskSource()
        scheduler = Scheduler(1)
        scheduler.callback(SchedulerProto.scheduled_task_postponed, signal_watcher)

        with ThreadRunner.task(scheduler):
            scheduler.subscribe(source)

            source.schedule_record(ScheduleRecord(sample_tasks.LongRunningTask(terminate_method=False), source))
            source.schedule_record(ScheduleRecord(sample_tasks.LongRunningTask(terminate_method=False), source))
            signal_watcher.wait(100)

    def test_signal_task_expired(self, signal_watcher: SignalWatcher, sample_tasks: SampleTasks) -> None:
        source = InstantTaskSource()
        scheduler = Scheduler(1)
        scheduler.callback(SchedulerProto.scheduled_task_expired, signal_watcher)

        with ThreadRunner.task(scheduler):
            scheduler.subscribe(source)

            source.schedule_record(ScheduleRecord(sample_tasks.LongRunningTask(terminate_method=False), source, ttl=1))
            signal_watcher.wait(100)

    def test_signal_task_started(self, signal_watcher: SignalWatcher, sample_tasks: SampleTasks) -> None:
        source = InstantTaskSource()
        scheduler = Scheduler(1)
        scheduler.callback(SchedulerProto.scheduled_task_started, signal_watcher)

        with ThreadRunner.task(scheduler):
            scheduler.subscribe(source)

            source.schedule_record(ScheduleRecord(sample_tasks.LongRunningTask(terminate_method=False), source))
            signal_watcher.wait(100)

    def test_signal_task_complete(self, signal_watcher: SignalWatcher, sample_tasks: SampleTasks) -> None:
        source = InstantTaskSource()
        scheduler = Scheduler(1)
        scheduler.callback(SchedulerProto.scheduled_task_completed, signal_watcher)

        with ThreadRunner.task(scheduler):
            scheduler.subscribe(source)

            source.schedule_record(ScheduleRecord(sample_tasks.DummyTask(), source))
            signal_watcher.wait(100)
