# -*- coding: utf-8 -*-

import typing

if typing.TYPE_CHECKING:
    # noinspection PyUnresolvedReferences
    from conftest import SampleTasks

from pyknic.lib.signals.proto import Signal, SignalSourceProto

from pyknic.lib.tasks.proto import ScheduleSourceProto
from pyknic.lib.tasks.scheduler.record import ScheduleRecord
from pyknic.lib.tasks.scheduler.plain_sources import InstantTaskSource


class TestInstantTaskSource:

    def test(self, sample_tasks: 'SampleTasks') -> None:
        callback_result = []

        def callback(src: SignalSourceProto, signal: Signal, value: ScheduleRecord) -> None:
            callback_result.append(value)

        source = InstantTaskSource()
        assert(isinstance(source, ScheduleSourceProto))

        record = ScheduleRecord(sample_tasks.DummyTask(), source)
        source.callback(source.task_scheduled, callback)
        source.schedule_record(record)
        assert(callback_result == [record])
