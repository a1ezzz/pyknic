# -*- coding: utf-8 -*-

import pytest

from pyknic.lib.capability import iscapable, CapabilityDescriptor

from pyknic.lib.tasks.proto import RequirementsLoopError, TaskStartError, TaskStopError, NoSuchTaskError, TaskProto
from pyknic.lib.tasks.proto import TaskResult


def test_exceptions() -> None:
    assert(issubclass(RequirementsLoopError, Exception) is True)
    assert(issubclass(TaskStartError, Exception) is True)
    assert(issubclass(TaskStopError, Exception) is True)
    assert(issubclass(NoSuchTaskError, Exception) is True)


def test_abstract() -> None:
    pytest.raises(TypeError, TaskProto)
    pytest.raises(NotImplementedError, TaskProto.start, None)


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
        task.emit(TaskProto.task_stopped)
        task.emit(TaskProto.task_terminated)
        task.emit(TaskProto.task_completed, TaskResult())
