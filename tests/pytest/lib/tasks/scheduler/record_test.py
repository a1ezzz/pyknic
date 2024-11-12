# -*- coding: utf-8 -*-

import typing

from pyknic.lib.tasks.proto import ScheduleRecordProto, ScheduledTaskPostponePolicy
from pyknic.lib.tasks.scheduler.record import ScheduleRecord

if typing.TYPE_CHECKING:
    # noinspection PyUnresolvedReferences
    from conftest import SampleTasks


class TestScheduleRecord:

    def test(self, sample_tasks: 'SampleTasks') -> None:
        task1 = sample_tasks.DummyTask()
        record = ScheduleRecord(task1)
        assert(isinstance(record, ScheduleRecord) is True)
        assert(isinstance(record, ScheduleRecordProto) is True)
        assert(record.task() is task1)
        assert(record.group_id() is None)
        assert(record.ttl() is None)
        assert(record.simultaneous_runs() == 0)
        assert(record.postpone_policy() == ScheduledTaskPostponePolicy.wait)

        task2 = sample_tasks.DummyTask()
        record = ScheduleRecord(
            task2,
            group_id='task_group',
            ttl=10,
            simultaneous_runs=2,
            postpone_policy=ScheduledTaskPostponePolicy.drop
        )

        assert(record.task() is task2)
        assert(record.group_id() == 'task_group')
        assert(record.ttl() == 10)
        assert(record.simultaneous_runs() == 2)
        assert(record.postpone_policy() == ScheduledTaskPostponePolicy.drop)
