# -*- coding: utf-8 -*-

import threading
import typing

import pytest

from pyknic.lib.tasks.proto import SchedulerProto
from pyknic.lib.tasks.plain_task import PlainTask
from pyknic.lib.tasks.threaded_task import ThreadedTask
from pyknic.lib.tasks.scheduler.plain_sources import InstantTaskSource
from pyknic.lib.tasks.scheduler.scheduler import Scheduler
from pyknic.lib.tasks.scheduler.record import ScheduleRecord
from pyknic.lib.signals.proxy import QueueCallbackException


class TestScheduler:

    class SynCallback:

        def __init__(self) -> None:
            self.event = threading.Event()

        def __call__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
            self.event.set()

        @staticmethod
        def flush(source: InstantTaskSource) -> None:
            syn = TestScheduler.SynCallback()
            source.schedule_record(ScheduleRecord(PlainTask(syn)))
            syn.event.wait()

    def test(
        self,
        callbacks_registry: 'CallbackRegistry',  # type: ignore[name-defined]  # noqa: F821  # conftest issue
    ) -> None:
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

    def test_signal_task_scheduled(
        self,
        signal_watcher: 'SignalWatcher'  # type: ignore[name-defined]  # noqa: F821  # conftest issue
    ) -> None:
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

    def test_signal_task_dropped(self) -> None:
        pass

    def test_signal_task_postponed(self) -> None:
        pass

    def test_signal_task_expired(self) -> None:
        pass

    def test_signal_task_started(self) -> None:
        pass

    def test_signal_task_complete(self) -> None:
        pass
