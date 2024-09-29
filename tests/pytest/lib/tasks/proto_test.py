# -*- coding: utf-8 -*-

import pytest

from pyknic.lib.capability import iscapable, CapabilityDescriptor

from pyknic.lib.tasks.proto import RequirementsLoopError, TaskStartError, TaskStopError, NoSuchTaskError, TaskProto
from pyknic.lib.tasks.proto import TaskResult, ScheduleRecordProto, SchedulerProto, ScheduledTaskPostponePolicy


def test_exceptions() -> None:
    assert(issubclass(RequirementsLoopError, Exception) is True)
    assert(issubclass(TaskStartError, Exception) is True)
    assert(issubclass(TaskStopError, Exception) is True)
    assert(issubclass(NoSuchTaskError, Exception) is True)


def test_abstract() -> None:
    pytest.raises(TypeError, TaskProto)
    pytest.raises(NotImplementedError, TaskProto.start, None)

    pytest.raises(TypeError, ScheduleRecordProto)
    pytest.raises(NotImplementedError, ScheduleRecordProto.task, None)

    pytest.raises(TypeError, SchedulerProto)
    pytest.raises(NotImplementedError, SchedulerProto.subscribe, None, None)
    pytest.raises(NotImplementedError, SchedulerProto.unsubscribe, None, None)


class TestTaskProto:

    class Task(TaskProto):

        def start(self) -> None:
            pass

    def test(self) -> None:
        assert(isinstance(
            TaskProto.stop.__pyknic_capability__,  # type: ignore[attr-defined]  # mypy and metaclass issues
            CapabilityDescriptor
        ))
        assert(isinstance(
            TaskProto.terminate.__pyknic_capability__,  # type: ignore[attr-defined]  # mypy and metaclass issues
            CapabilityDescriptor
        ))

        task = TestTaskProto.Task()
        pytest.raises(NotImplementedError, task.stop)
        pytest.raises(NotImplementedError, task.terminate)

        assert(iscapable(task, TaskProto.stop) is False)
        assert(iscapable(task, TaskProto.terminate) is False)

        task.emit(TaskProto.task_started)
        task.emit(TaskProto.task_completed, TaskResult())


class TestScheduleRecordProto:

    def test(self) -> None:

        class Task(TaskProto):

            def start(self) -> None:
                pass

        class Record(ScheduleRecordProto):
            def task(self) -> TaskProto:
                return Task()

        record = Record()
        assert(record.group_id() is None)
        assert(record.ttl() is None)
        assert(record.simultaneous_runs() == 0)
        assert(record.postpone_policy() == ScheduledTaskPostponePolicy.wait)
