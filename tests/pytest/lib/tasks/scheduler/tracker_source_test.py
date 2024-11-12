# -*- coding: utf-8 -*-

import pytest
import typing

from pyknic.lib.tasks.scheduler.plain_sources import InstantTaskSource
from pyknic.lib.tasks.scheduler.record import ScheduleRecord

if typing.TYPE_CHECKING:
    # noinspection PyUnresolvedReferences
    from conftest import SampleTasks

from pyknic.lib.tasks.proto import ScheduleSourceProto, SchedulerProto, SchedulerFeedback, ScheduledTaskPostponePolicy
from pyknic.lib.tasks.scheduler.tracker_source import TaskTrackerSource
from pyknic.lib.tasks.scheduler.scheduler import Scheduler
from pyknic.lib.tasks.threaded_task import ThreadedTask


class TestTaskTrackerSource:

    def test(self) -> None:

        class SampleScheduler(SchedulerProto):

            def subscribe(self, schedule_source: ScheduleSourceProto) -> None:
                pass

            def unsubscribe(self, schedule_source: ScheduleSourceProto) -> None:
                pass

        source = TaskTrackerSource()
        assert(source.scheduler() is None)
        scheduler = SampleScheduler()

        with pytest.raises(ValueError):
            source.scheduler_feedback(scheduler, SchedulerFeedback.source_unsubscribed)

        source.scheduler_feedback(scheduler, SchedulerFeedback.source_subscribed)
        assert(source.scheduler() is scheduler)

        with pytest.raises(ValueError):
            source.scheduler_feedback(scheduler, SchedulerFeedback.source_subscribed)

        source.scheduler_feedback(scheduler, SchedulerFeedback.source_unsubscribed)
        assert(source.scheduler() is None)

    def test_tracker_wait_succeeded(self, sample_tasks: 'SampleTasks') -> None:
        source = TaskTrackerSource()

        scheduler = Scheduler()
        threaded_scheduler = ThreadedTask(scheduler)
        threaded_scheduler.start()
        scheduler.subscribe(source)

        record = ScheduleRecord(sample_tasks.LongRunningTask(), postpone_policy=ScheduledTaskPostponePolicy.drop)
        assert(source.wait_response(record) == SchedulerProto.scheduled_task_started)

        threaded_scheduler.stop()
        threaded_scheduler.join()

    def test_tracker_wait_failed(self, sample_tasks: 'SampleTasks') -> None:
        source = TaskTrackerSource()
        instant_source = InstantTaskSource()

        scheduler = Scheduler(1)
        threaded_scheduler = ThreadedTask(scheduler)
        threaded_scheduler.start()
        scheduler.subscribe(source)
        scheduler.subscribe(instant_source)

        first_record = ScheduleRecord(sample_tasks.LongRunningTask(), postpone_policy=ScheduledTaskPostponePolicy.drop)
        instant_source.schedule_record(first_record)

        second_record = ScheduleRecord(sample_tasks.LongRunningTask(), postpone_policy=ScheduledTaskPostponePolicy.drop)
        assert(source.wait_response(second_record) == SchedulerProto.scheduled_task_dropped)

        threaded_scheduler.stop()
        threaded_scheduler.join()

    def test_tracker_wait_expired(self, sample_tasks: 'SampleTasks') -> None:
        source = TaskTrackerSource()
        instant_source = InstantTaskSource()

        scheduler = Scheduler(1)
        threaded_scheduler = ThreadedTask(scheduler)
        threaded_scheduler.start()
        scheduler.subscribe(source)
        scheduler.subscribe(instant_source)

        first_record = ScheduleRecord(sample_tasks.LongRunningTask(), postpone_policy=ScheduledTaskPostponePolicy.drop)
        instant_source.schedule_record(first_record)

        second_record = ScheduleRecord(
            sample_tasks.LongRunningTask(),
            postpone_policy=ScheduledTaskPostponePolicy.drop,
            ttl=1
        )
        assert(source.wait_response(second_record) == SchedulerProto.scheduled_task_expired)

        threaded_scheduler.stop()
        threaded_scheduler.join()

    def test_exception(self, sample_tasks: 'SampleTasks') -> None:
        source = TaskTrackerSource()
        assert(source.scheduler() is None)
        scheduler = Scheduler()
        threaded_scheduler = ThreadedTask(scheduler)
        threaded_scheduler.start()

        with pytest.raises(ValueError):
            source.scheduler_feedback(scheduler, 'feedback')  # type: ignore[arg-type]  # this is a test itself

        with pytest.raises(ValueError):
            source.wait_response(ScheduleRecord(
                sample_tasks.LongRunningTask(),
                postpone_policy=ScheduledTaskPostponePolicy.drop,
            ))

        scheduler.subscribe(source)

        with pytest.raises(ValueError):
            source.wait_response(ScheduleRecord(sample_tasks.LongRunningTask()))

        source.wait_response(ScheduleRecord(
            sample_tasks.LongRunningTask(),
            postpone_policy=ScheduledTaskPostponePolicy.drop,
        ))

        threaded_scheduler.stop()
        threaded_scheduler.join()
