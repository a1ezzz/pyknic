# -*- coding: utf-8 -*-

import threading
import typing
import pytest

from pyknic.lib.tasks.proto import TaskProto, ScheduleSourceProto
from pyknic.lib.datalog.proto import DatalogProto
from pyknic.lib.datalog.datalog import Datalog
from pyknic.lib.tasks.scheduler.record import ScheduleRecord


class SampleTasks:

    class DummyTask(TaskProto):

        def start(self) -> None:
            pass

    class LongRunningTask(TaskProto):

        def __init__(self, stop_method: bool = True, terminate_method: bool = True):
            TaskProto.__init__(self)
            self.__event = threading.Event()

            if stop_method:
                self.append_capability(TaskProto.stop, self.__stop_func)

            if terminate_method:
                self.append_capability(TaskProto.terminate, self.__stop_func)

        def start(self) -> None:
            self.__event.clear()
            self.__event.wait()

        def __stop_func(self) -> None:
            self.__event.set()

    class PlainRecord(ScheduleRecord):

        def __init__(self, task: TaskProto, **kwargs: typing.Any) -> None:
            ScheduleRecord.__init__(self, task, SampleTasks.DummySource(), **kwargs)

    class DummySource(ScheduleSourceProto):
        pass


@pytest.fixture
def sample_tasks() -> type:
    return SampleTasks


@pytest.fixture
def empty_datalog() -> DatalogProto:
    return Datalog()
