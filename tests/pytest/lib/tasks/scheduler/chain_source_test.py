# -*- coding: utf-8 -*-
import threading
import time

import pytest
import typing
import uuid

from datetime import datetime, timezone

if typing.TYPE_CHECKING:
    # noinspection PyUnresolvedReferences
    from conftest import SampleTasks

from pyknic.lib.registry import APIRegistry, register_api
from pyknic.lib.datalog.proto import DatalogProto
from pyknic.lib.datalog.datalog import Datalog
from pyknic.lib.signals.extra import SignalWaiter
from pyknic.lib.tasks.scheduler.chain_source import ChainedTaskState, ChainedTaskLogEntry, ChainedTasksSource
from pyknic.lib.tasks.scheduler.chain_source import ChainedTask
from pyknic.lib.tasks.scheduler.record import ScheduleRecord
from pyknic.lib.tasks.scheduler.scheduler import Scheduler
from pyknic.lib.tasks.scheduler.plain_sources import InstantTaskSource
from pyknic.lib.tasks.proto import TaskResult, SchedulerProto, SchedulerFeedback
from pyknic.lib.tasks.threaded_task import ThreadedTask


class SourceTestHelper:

    def __init__(self) -> None:
        self.scheduler = Scheduler()
        self.scheduler_thread = ThreadedTask(self.scheduler)
        self.api_registry = APIRegistry()

    def start(self) -> None:
        self.scheduler_thread.start()

    def stop(self) -> None:
        self.scheduler_thread.stop()
        self.scheduler_thread.wait()
        self.scheduler_thread.join()


@pytest.fixture
def source_helper(request: pytest.FixtureRequest) -> typing.Generator[SourceTestHelper, None, None]:
    helper = SourceTestHelper()
    helper.start()

    yield helper
    helper.stop()


class TestChainedTask:

    def test(self, source_helper: SourceTestHelper) -> None:
        class Task(ChainedTask):
            def start(self) -> None:
                pass

        source = ChainedTasksSource(registry=source_helper.api_registry)
        datalog = source.datalog()
        uid = uuid.uuid4()
        task = Task.create(datalog, 'sample-api-id', uid)
        assert(task.uid() == uid)
        assert(task.datalog() is datalog)
        assert(task.api_id() == 'sample-api-id')

    def test_wait_for_result(self, source_helper: SourceTestHelper) -> None:

        event = threading.Event()
        result_object = object()
        result = TaskResult(result=result_object)

        @register_api(source_helper.api_registry, 'test-task')
        class Task(ChainedTask):
            def start(self) -> None:
                nonlocal event, result
                time.sleep(0.5)
                event.set()

                self.save_result(result)

        source = ChainedTasksSource(registry=source_helper.api_registry)
        source_thread = ThreadedTask(source)
        source_thread.start()

        source_helper.scheduler.subscribe(source)
        source.execute('test-task')

        task = Task(source.datalog(), 'task', uuid.uuid4())
        assert(task.wait_for('test-task') is result)
        assert(source.wait_for(source.datalog(), 'test-task') is result)

        source_thread.stop()
        source_thread.wait()
        source_thread.join()

    def test_wait_for_none(self, source_helper: SourceTestHelper) -> None:

        event = threading.Event()

        @register_api(source_helper.api_registry, 'test-task')
        class Task(ChainedTask):
            def start(self) -> None:
                nonlocal event
                time.sleep(0.5)
                event.set()

        source = ChainedTasksSource(registry=source_helper.api_registry)
        source_thread = ThreadedTask(source)
        source_thread.start()

        source_helper.scheduler.subscribe(source)
        source.execute('test-task')

        task = Task(source.datalog(), 'task', uuid.uuid4())
        assert(task.wait_for('test-task') is None)
        assert(source.wait_for(source.datalog(), 'test-task') is None)

        source_thread.stop()
        source_thread.wait()
        source_thread.join()


class TestChainedTaskLogEntry:

    def test(self) -> None:
        api_id = 'super_class'
        uid = uuid.uuid4()
        state = ChainedTaskState.completed
        result = TaskResult()
        event_datetime = datetime.now(timezone.utc)

        entry = ChainedTaskLogEntry(api_id, uid, state, result)
        assert(entry.api_id is api_id)
        assert(entry.uid is uid)
        assert(entry.event_datetime >= event_datetime)
        assert(entry.state is state)
        assert(entry.result is result)

    def test_exceptions(self) -> None:
        api_id = 'super_class'
        uid = uuid.uuid4()
        state = ChainedTaskState.completed
        result = TaskResult()

        entry = ChainedTaskLogEntry(api_id, uid, state, result)

        with pytest.raises(AttributeError):
            entry.api_id = "bad_class"  # type: ignore[misc]  # it is a test =)


class TestChainedTasksSource:

    class Task(ChainedTask):

        def __init__(self, datalog: DatalogProto, api_id: str, uid: uuid.UUID) -> None:
            ChainedTask.__init__(self, datalog, api_id, uid)
            self.event = threading.Event()

        def start(self) -> None:
            self.event.wait()

        def stop(self) -> None:
            self.event.set()

    def test_plain_start(self, source_helper: SourceTestHelper) -> None:
        source = ChainedTasksSource(registry=source_helper.api_registry)
        source_thread = ThreadedTask(source)
        source_thread.start()

        @register_api(source_helper.api_registry, 'test-task')
        class TestClass(TestChainedTasksSource.Task):
            pass

        assert(source.started_task('test-task') is None)
        source_helper.scheduler.subscribe(source)
        source.execute('test-task')
        assert(source.started_task('test-task') is not None)

        source_thread.stop()
        source_thread.wait()
        source_thread.join()

    def test_dependent_start(self, source_helper: SourceTestHelper) -> None:
        source = ChainedTasksSource(registry=source_helper.api_registry)
        source_thread = ThreadedTask(source)
        source_thread.start()

        @register_api(source_helper.api_registry, 'test-task1')
        class TestClass1(TestChainedTasksSource.Task):
            pass

        @register_api(source_helper.api_registry, 'test-task2')
        class TestClass2(TestChainedTasksSource.Task):

            @classmethod
            def dependencies(cls) -> typing.Optional[typing.Set[str]]:
                return {'test-task1'}

        @register_api(source_helper.api_registry, 'test-task3')
        class TestClass3(TestChainedTasksSource.Task):

            @classmethod
            def dependencies(cls) -> typing.Optional[typing.Set[str]]:
                return {'test-task2'}

        source_helper.scheduler.subscribe(source)
        source.execute('test-task1')
        source.execute('test-task3')

        assert(source.started_task('test-task1') is not None)
        assert(source.started_task('test-task2') is not None)
        assert(source.started_task('test-task3') is not None)

        source_thread.stop()
        source_thread.wait()
        source_thread.join()

    def test_skip_started_coverage(self, source_helper: SourceTestHelper) -> None:
        source = ChainedTasksSource(registry=source_helper.api_registry)
        source_thread = ThreadedTask(source)
        source_thread.start()

        @register_api(source_helper.api_registry, 'test-task1')
        class TestClass1(TestChainedTasksSource.Task):
            pass

        @register_api(source_helper.api_registry, 'test-task2')
        class TestClass2(TestChainedTasksSource.Task):

            @classmethod
            def dependencies(cls) -> typing.Optional[typing.Set[str]]:
                return {'test-task1'}

        @register_api(source_helper.api_registry, 'test-task3')
        class TestClass3(TestChainedTasksSource.Task):

            @classmethod
            def dependencies(cls) -> typing.Optional[typing.Set[str]]:
                return {'test-task2'}

        source_helper.scheduler.subscribe(source)
        source.execute('test-task1')

        source_thread.stop()
        source_thread.wait()
        source_thread.join()

    def test_exception(self, source_helper: SourceTestHelper) -> None:
        source = ChainedTasksSource(registry=source_helper.api_registry)
        source_thread = ThreadedTask(source)
        source_thread.start()

        with pytest.raises(ValueError):
            source.scheduler_feedback(source_helper.scheduler, SchedulerFeedback.source_unsubscribed)

        with pytest.raises(ValueError):
            source.scheduler_feedback(source_helper.scheduler, 1)  # type: ignore[arg-type]  # just a test

        @register_api(source_helper.api_registry, 'test-task1')
        class TestClass1(TestChainedTasksSource.Task):
            pass

        @register_api(source_helper.api_registry, 'test-task2')
        class TestClass2(TestChainedTasksSource.Task):

            @classmethod
            def dependencies(cls) -> typing.Optional[typing.Set[str]]:
                return {'test-task3'}

        @register_api(source_helper.api_registry, 'test-task3')
        class TestClass3(TestChainedTasksSource.Task):

            @classmethod
            def dependencies(cls) -> typing.Optional[typing.Set[str]]:
                return {'test-task3'}

        with pytest.raises(ValueError):
            source.execute('test-task1')

        source_helper.scheduler.subscribe(source)

        with pytest.raises(ValueError):
            source.scheduler_feedback(source_helper.scheduler, SchedulerFeedback.source_subscribed)

        source.execute('test-task1')

        with pytest.raises(ValueError):
            source.execute('test-task1')

        with pytest.raises(ValueError):
            source.execute('test-task2')

        with pytest.raises(ValueError):
            source.execute('test-task3')

        source_thread.stop()
        source_thread.wait()
        source_thread.join()

    def test_scheduler_exception(self, source_helper: SourceTestHelper, sample_tasks: 'SampleTasks') -> None:
        scheduler = Scheduler(1)
        scheduler_thread = ThreadedTask(scheduler)
        scheduler_thread.start()

        instant_source = InstantTaskSource()

        source = ChainedTasksSource(registry=source_helper.api_registry)
        source_thread = ThreadedTask(source)
        source_thread.start()

        @register_api(source_helper.api_registry, 'test-task1')
        class TestClass1(TestChainedTasksSource.Task):
            pass

        scheduler.subscribe(instant_source)
        instant_source.schedule_record(ScheduleRecord(sample_tasks.LongRunningTask(), source))  # scheduler is full now

        scheduler.subscribe(source)
        with pytest.raises(ValueError):
            source.execute('test-task1')

        source_thread.stop()
        source_thread.wait()
        source_thread.join()

        scheduler_thread.stop()
        scheduler_thread.wait()
        scheduler_thread.join()

    def test_datalog(self, source_helper: SourceTestHelper) -> None:
        source = ChainedTasksSource(registry=source_helper.api_registry)
        assert(isinstance(source.datalog(), DatalogProto) is True)

        datalog = Datalog()
        source = ChainedTasksSource(datalog=datalog, registry=source_helper.api_registry)
        assert(source.datalog() is datalog)

    def test_datalog_entries(self, source_helper: SourceTestHelper) -> None:
        source = ChainedTasksSource(registry=source_helper.api_registry)
        source_thread = ThreadedTask(source)
        source_thread.start()

        @register_api(source_helper.api_registry, 'test-task')
        class TestClass1(ChainedTask):
            event = threading.Event()

            def start(self) -> None:
                self.event.wait()

        assert(list(source.datalog().iterate()) == [])

        source_helper.scheduler.subscribe(source)
        waiter = SignalWaiter(source_helper.scheduler, SchedulerProto.scheduled_task_completed)
        source.execute('test-task')

        datalog = source.datalog()
        datalog_list = list(datalog.iterate())
        assert(len(datalog_list) == 1)
        assert(isinstance(datalog_list[0], ChainedTaskLogEntry) is True)
        assert(datalog_list[0].api_id == "test-task")
        assert(datalog_list[0].state == ChainedTaskState.started)
        assert(datalog_list[0].result is None)

        TestClass1.event.set()
        waiter.wait()

        source_thread.stop()
        source_thread.wait()
        source_thread.join()

        datalog_list = list(datalog.iterate())
        assert(len(datalog_list) == 2)
