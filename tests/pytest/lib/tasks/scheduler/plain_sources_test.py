# -*- coding: utf-8 -*-

from pyknic.lib.signals.proto import Signal, SignalSourceProto

from pyknic.lib.tasks.proto import ScheduleSourceProto, TaskProto
from pyknic.lib.tasks.scheduler.record import ScheduleRecord
from pyknic.lib.tasks.scheduler.source import InstantTaskSource


class TestInstantTaskSource:

    class Sample(TaskProto):
        def start(self) -> None:
            pass

    def test(self) -> None:
        callback_result = []

        def callback(src: SignalSourceProto, signal: Signal, value: ScheduleRecord) -> None:
            callback_result.append(value)

        source = InstantTaskSource()
        assert(isinstance(source, ScheduleSourceProto))

        record = ScheduleRecord(TestInstantTaskSource.Sample())
        source.callback(source.task_scheduled, callback)
        source.schedule_record(record)
        assert(callback_result == [record])
