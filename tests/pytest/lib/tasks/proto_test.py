# -*- coding: utf-8 -*-

import asyncio
import pytest
import typing

if typing.TYPE_CHECKING:
    # noinspection PyUnresolvedReferences
    from conftest import SampleTasks

from pyknic.lib.capability import iscapable, CapabilityDescriptor

from pyknic.lib.tasks.proto import TaskStartError, TaskStopError, NoSuchTaskError, TaskProto
from pyknic.lib.tasks.proto import TaskResult, ScheduleRecordProto, SchedulerProto, ScheduledTaskPostponePolicy
from pyknic.lib.tasks.proto import TaskExecutorProto, ScheduleSourceProto

from fixtures.asyncio import pyknic_async_test


def test_exceptions() -> None:
    assert(issubclass(TaskStartError, Exception) is True)
    assert(issubclass(TaskStopError, Exception) is True)
    assert(issubclass(NoSuchTaskError, Exception) is True)


@pyknic_async_test
async def test_abstract(module_event_loop: asyncio.AbstractEventLoop) -> None:
    pytest.raises(TypeError, TaskProto)
    pytest.raises(NotImplementedError, TaskProto.start, None)

    pytest.raises(TypeError, ScheduleRecordProto)
    pytest.raises(NotImplementedError, ScheduleRecordProto.task, None)
    pytest.raises(NotImplementedError, ScheduleRecordProto.source, None)

    pytest.raises(TypeError, SchedulerProto)
    pytest.raises(NotImplementedError, SchedulerProto.subscribe, None, None)
    pytest.raises(NotImplementedError, SchedulerProto.unsubscribe, None, None)

    pytest.raises(NotImplementedError, ScheduleSourceProto.scheduler_feedback, None, None, None)  # capability test

    pytest.raises(TypeError, TaskExecutorProto)
    pytest.raises(NotImplementedError, TaskExecutorProto.submit_task, None, None)
    pytest.raises(NotImplementedError, TaskExecutorProto.complete_task, None, None)
    pytest.raises(NotImplementedError, TaskExecutorProto.wait_task, None, None, None)

    with pytest.raises(NotImplementedError):
        await TaskExecutorProto.async_wait_task(None, None)  # type: ignore[arg-type]  # it is just a test

    pytest.raises(NotImplementedError, TaskExecutorProto.tasks, None)


class TestTaskProto:

    def test(self, sample_tasks: 'SampleTasks') -> None:
        assert(isinstance(
            TaskProto.stop.__pyknic_capability__,  # type: ignore[attr-defined]  # mypy and metaclass issues
            CapabilityDescriptor
        ))
        assert(isinstance(
            TaskProto.terminate.__pyknic_capability__,  # type: ignore[attr-defined]  # mypy and metaclass issues
            CapabilityDescriptor
        ))

        task = sample_tasks.DummyTask()
        pytest.raises(NotImplementedError, task.stop)
        pytest.raises(NotImplementedError, task.terminate)

        assert(iscapable(task, TaskProto.stop) is False)
        assert(iscapable(task, TaskProto.terminate) is False)

        task.emit(TaskProto.task_started)
        task.emit(TaskProto.task_completed, TaskResult())

        assert(TaskProto.task_name(None) is None)  # type: ignore[arg-type]


class TestScheduleRecordProto:

    def test(self, sample_tasks: 'SampleTasks') -> None:

        class Record(ScheduleRecordProto):
            def task(self) -> TaskProto:
                return sample_tasks.DummyTask()

            def source(self) -> 'ScheduleSourceProto':
                return object()  # type: ignore[return-value]  # just a test

        record = Record()
        assert(record.group_id() is None)
        assert(record.ttl() is None)
        assert(record.simultaneous_runs() == 0)
        assert(record.postpone_policy() == ScheduledTaskPostponePolicy.wait)
