# -*- coding: utf-8 -*-

from pyknic.lib.tasks.proto import ScheduleRecordProto, ScheduledTaskPostponePolicy, TaskProto
from pyknic.lib.tasks.scheduler.record import ScheduleRecord


class TestScheduleRecord:

    class SampleTask(TaskProto):
        def start(self) -> None:
            pass

    def test(self) -> None:
        task1 = TestScheduleRecord.SampleTask()
        record = ScheduleRecord(task1)
        assert(isinstance(record, ScheduleRecord) is True)
        assert(isinstance(record, ScheduleRecordProto) is True)
        assert(record.task() is task1)
        assert(record.group_id() is None)
        assert(record.ttl() is None)
        assert(record.simultaneous_runs() == 0)
        assert(record.postpone_policy() == ScheduledTaskPostponePolicy.wait)

        task2 = TestScheduleRecord.SampleTask()
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
