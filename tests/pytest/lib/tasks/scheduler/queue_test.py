# -*- coding: utf-8 -*-

import pytest
import time
import typing

from datetime import datetime, timezone

if typing.TYPE_CHECKING:
    # noinspection PyUnresolvedReferences
    from conftest import SignalsRegistry, SampleTasks

from pyknic.lib.signals.proto import SignalSourceProto
from pyknic.lib.tasks.plain_task import PlainTask
from pyknic.lib.tasks.proto import ScheduledTaskPostponePolicy, ScheduleRecordProto
from pyknic.lib.tasks.scheduler.queue import SchedulerQueue


scheduler_queue_test_case = (
    (
        {'policy': None, 'group': None},
    ),

    (
        {'policy': ScheduledTaskPostponePolicy.drop, 'group': None},
    ),

    (
        {'policy': None, 'group': 'group1'},
        {'policy': None, 'group': 'group2'},
    ),

    (
        {'policy': ScheduledTaskPostponePolicy.wait, 'group': 'group1'},
        {'policy': ScheduledTaskPostponePolicy.wait, 'group': 'group2'},
        {'policy': ScheduledTaskPostponePolicy.wait, 'group': 'group1'},
    ),

    (
        {'policy': ScheduledTaskPostponePolicy.keep_last, 'group': 'group1'},
        {'policy': ScheduledTaskPostponePolicy.keep_last, 'group': 'group2'},
        {'policy': ScheduledTaskPostponePolicy.keep_last, 'group': None},
        {'policy': None, 'group': None},
        {'policy': ScheduledTaskPostponePolicy.keep_last, 'group': 'group1'},
        {'policy': ScheduledTaskPostponePolicy.keep_last, 'group': None},
    ),

    (
        {'policy': None, 'group': 'group1'},
        {'policy': ScheduledTaskPostponePolicy.keep_first, 'group': 'group2'},
        {'policy': ScheduledTaskPostponePolicy.keep_first, 'group': None},
        {'policy': None, 'group': None},
        {'policy': None, 'group': 'group1'},
        {'policy': ScheduledTaskPostponePolicy.keep_first, 'group': 'group1'},
        {'policy': ScheduledTaskPostponePolicy.keep_first, 'group': None},
    ),
)


class TestSchedulerPostponeQueue:

    def flush_records(self, queue: SchedulerQueue) -> typing.List[ScheduleRecordProto]:
        result = []
        next_record = queue.next_record()
        while next_record:
            result.append(next_record)
            next_record = queue.next_record()

        return result

    def test_plain(self, sample_tasks: 'SampleTasks') -> None:
        queue = SchedulerQueue()
        assert(isinstance(queue, SignalSourceProto) is True)

        record = sample_tasks.PlainRecord(PlainTask(lambda: None))
        queue.postpone(record)

        assert(self.flush_records(queue) == [record])

    @pytest.mark.parametrize(
        "records, result_indices", tuple(
            zip(
                scheduler_queue_test_case,
                (
                    (0, ),
                    tuple(),
                    (0, 1),
                    (0, 1, 2),
                    (1, 2, 3, 4, 5),
                    (0, 1, 2, 3, 6),
                )
            )
        )
    )
    def test_groups(
        self,
        sample_tasks: 'SampleTasks',
        records: typing.Tuple[typing.Dict[str, typing.Any]],
        result_indices: typing.Tuple[int]
    ) -> None:
        queue = SchedulerQueue()
        task = PlainTask(lambda: None)
        input_records = [
            sample_tasks.PlainRecord(task, postpone_policy=x['policy'], group_id=x['group']) for x in records
        ]
        result_records = [input_records[x] for x in result_indices]

        for i in input_records:
            queue.postpone(i)

        assert(self.flush_records(queue) == result_records)

    def test_ttl(self, sample_tasks: 'SampleTasks', signals_registry: 'SignalsRegistry') -> None:
        queue = SchedulerQueue()
        queue.callback(SchedulerQueue.task_expired, signals_registry)
        task = PlainTask(lambda: None)

        record1 = sample_tasks.PlainRecord(  # this one is kept
            task, ttl=(datetime.now(timezone.utc).timestamp() + 1000)
        )
        record2 = sample_tasks.PlainRecord(  # this one is dropped
            task, ttl=(datetime.now(timezone.utc).timestamp() - 10)
        )
        queue.postpone(record1)
        queue.postpone(record2)

        assert(self.flush_records(queue) == [record1])
        assert(signals_registry.dump(True) == [(queue, SchedulerQueue.task_expired, record2)])

    def test_ttl_next_record(self, sample_tasks: 'SampleTasks', signals_registry: 'SignalsRegistry') -> None:
        queue = SchedulerQueue()
        queue.callback(SchedulerQueue.task_expired, signals_registry)
        task = PlainTask(lambda: None)
        time_delta = 0.5

        record = sample_tasks.PlainRecord(task, ttl=(datetime.now(timezone.utc).timestamp() + time_delta))
        queue.postpone(record)

        time.sleep(time_delta * 2)
        assert(self.flush_records(queue) == [])
        assert(signals_registry.dump(True) == [(queue, SchedulerQueue.task_expired, record)])

    @pytest.mark.parametrize(
        "records, result_indices", tuple(
            zip(
                scheduler_queue_test_case,
                (
                    tuple(),
                    (0, ),
                    tuple(),
                    tuple(),
                    (0,),
                    (4, 5,),
                )
            )
        )
    )
    def test_dropped_signals(
        self,
        sample_tasks: 'SampleTasks',
        signals_registry: 'SignalsRegistry',
        records: typing.Tuple[typing.Dict[str, typing.Any]],
        result_indices: typing.Tuple[int]
    ) -> None:
        queue = SchedulerQueue()
        queue.callback(SchedulerQueue.task_dropped, signals_registry)

        task = PlainTask(lambda: None)
        input_records = [
            sample_tasks.PlainRecord(task, postpone_policy=x['policy'], group_id=x['group']) for x in records
        ]
        dropped_signals = [
            (queue, SchedulerQueue.task_dropped, input_records[x]) for x in result_indices
        ]

        for i in input_records:
            queue.postpone(i)

        assert(signals_registry.dump(True) == dropped_signals)

    @pytest.mark.parametrize(
        "records, result_indices", tuple(
            zip(
                scheduler_queue_test_case,
                (
                    (0, ),
                    tuple(),
                    (0, 1),
                    (0, 1, 2),
                    (0, 1, 2, 3, 4, 5),
                    (0, 1, 2, 3, 4, 6),
                )
            )
        )
    )
    def test_postponed_signals(
        self,
        sample_tasks: 'SampleTasks',
        signals_registry: 'SignalsRegistry',
        records: typing.Tuple[typing.Dict[str, typing.Any]],
        result_indices: typing.Tuple[int]
    ) -> None:
        queue = SchedulerQueue()
        queue.callback(SchedulerQueue.task_postponed, signals_registry)

        task = PlainTask(lambda: None)
        input_records = [
            sample_tasks.PlainRecord(task, postpone_policy=x['policy'], group_id=x['group']) for x in records
        ]
        postponed_signals = [
            (queue, SchedulerQueue.task_postponed, input_records[x]) for x in result_indices
        ]

        for i in input_records:
            queue.postpone(i)

        assert(signals_registry.dump(True) == postponed_signals)

    def test_filtered_next_record(self, sample_tasks: 'SampleTasks') -> None:
        queue = SchedulerQueue()
        task = PlainTask(lambda: None)

        record1 = sample_tasks.PlainRecord(task, group_id='group1')
        record2 = sample_tasks.PlainRecord(task, group_id='group2')
        queue.postpone(record1)
        queue.postpone(record2)

        assert(queue.next_record(lambda x: x.group_id() == 'group2') is record2)
        assert(queue.next_record(lambda x: x.group_id() == 'group2') is None)
        assert(queue.next_record() is record1)
        assert(queue.next_record() is None)

    def test_len(self, sample_tasks: 'SampleTasks') -> None:
        queue = SchedulerQueue()
        task = PlainTask(lambda: None)
        assert(len(queue) == 0)

        record1 = sample_tasks.PlainRecord(task, group_id='group1')
        record2 = sample_tasks.PlainRecord(task, group_id='group2')
        queue.postpone(record1)
        queue.postpone(record2)
        assert(len(queue) == 2)

        queue.next_record()
        assert(len(queue) == 1)
        queue.next_record()
        assert(len(queue) == 0)
