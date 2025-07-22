# -*- coding: utf-8 -*-
# pyknic/lib/tasks/scheduler/chain_source.py
#
# Copyright (C) 2024 the pyknic authors and contributors
# <see AUTHORS file>
#
# This file is part of pyknic.
#
# pyknic is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# pyknic is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with pyknic.  If not, see <http://www.gnu.org/licenses/>.

# TODO: more features:
#  - a chained task should register it's result in a datalog
#  - there should be a cooldown procedure for tasks that failed to run from the first time

import enum
import functools
import typing
import uuid

from contextlib import suppress
from datetime import datetime, timezone

from pyknic.lib.datalog.proto import DatalogProto
from pyknic.lib.datalog.datalog import Datalog
from pyknic.lib.registry import APIRegistryProto, APIRegistry
from pyknic.lib.signals.proto import SignalSourceProto, Signal
from pyknic.lib.signals.proxy import QueueProxy, QueueCallbackException
from pyknic.lib.signals.extra import SignalWaiter, BoundedCallback, ReceivedSignal
from pyknic.lib.tasks.proto import ScheduleSourceProto, TaskProto, TaskResult, ScheduledTaskPostponePolicy
from pyknic.lib.tasks.proto import ScheduleRecordProto
from pyknic.lib.tasks.proto import SchedulerFeedback, SchedulerProto
from pyknic.lib.tasks.scheduler.record import ScheduleRecord


__default_chained_tasks_registry__ = APIRegistry()


@enum.unique
class ChainedTaskState(enum.Enum):
    """ This represents a task state that will be kept in a log
    """
    started = enum.auto()    # a task started
    completed = enum.auto()  # a task finished with result (a task should report this)
    finalized = enum.auto()  # a task has been cleaned up


class ChainedTaskLogEntry:
    """ This is a record in a log, that describes an event happened to a task

    :note: this class was not made with dataclasses because it should be as much "immutable" as possible
    """

    def __init__(
        self,
        api_id: str,
        uid: uuid.UUID,
        state: ChainedTaskState,
        result: typing.Optional[TaskResult] = None
    ):
        """ Create an entry
        """
        self.__api_id = api_id
        self.__uid = uid
        self.__event_datetime = datetime.now(timezone.utc)
        self.__state = state
        self.__result = result

    @property
    def api_id(self) -> str:
        return self.__api_id

    @property
    def uid(self) -> uuid.UUID:
        return self.__uid

    @property
    def event_datetime(self) -> datetime:
        return self.__event_datetime

    @property
    def state(self) -> ChainedTaskState:
        return self.__state

    @property
    def result(self) -> typing.Optional[TaskResult]:
        return self.__result


# noinspection PyAbstractClass
class ChainedTask(TaskProto):
    """ This class may be started by a :class:`.ChainedTasksSource` that respects dependencies
    """

    def __init__(self, datalog: DatalogProto, api_id: str, uid: uuid.UUID):
        TaskProto.__init__(self)
        self.__datalog = datalog
        self.__api_id = api_id
        self.__uid = uid

    def datalog(self) -> DatalogProto:
        return self.__datalog

    def api_id(self) -> str:
        return self.__api_id

    def uid(self) -> uuid.UUID:
        return self.__uid

    @classmethod
    def create(cls, datalog: DatalogProto, api_id: str, uid: uuid.UUID) -> 'ChainedTask':
        """ Create a new task with:

        :param datalog: a log where result should be saved
        :param api_id: an id with which this task will be created
        :param uid: identifier of a task instance
        """
        return cls(datalog, api_id, uid)

    @classmethod
    def dependencies(cls) -> typing.Optional[typing.Set[str]]:
        """ Return task dependencies
        """
        return None

    def wait_for(self, api_id: str) -> typing.Optional[TaskResult]:
        return ChainedTasksSource.wait_for(self.datalog(), api_id)

    def save_result(self, result: typing.Any) -> None:
        self.datalog().append(
            ChainedTaskLogEntry(self.api_id(), self.uid(), ChainedTaskState.completed, TaskResult(result=result))
        )


class ChainedTasksSource(ScheduleSourceProto, TaskProto):
    """ This is a source for a scheduler that may start tasks and theirs dependencies
    """

    def __init__(
        self,
        datalog: typing.Optional[DatalogProto] = None,
        registry: typing.Optional[APIRegistryProto] = None
    ):
        """ Create a new source

        :param datalog: a log where tasks states are stored
        :param registry: a registry that holds classes (the "__default_chained_tasks_registry__" is used by default)
        """
        ScheduleSourceProto.__init__(self)
        TaskProto.__init__(self)

        self.__queue_proxy = QueueProxy()
        self.__source_uid = str(uuid.uuid4())

        self.__registry = registry if registry else __default_chained_tasks_registry__
        self.__datalog = datalog if datalog else Datalog()

        self.__scheduler: typing.Optional[SchedulerProto] = None
        self.__record_completed_clbk = BoundedCallback(self.__record_completed)

    def __record_completed(self, source: SignalSourceProto, signal: Signal, value: typing.Any) -> None:
        if value.source() is self:
            self.__datalog.append(ChainedTaskLogEntry(
                value.task().api_id(),
                value.task().uid(),
                ChainedTaskState.finalized
            ))

    def scheduler_feedback(self, scheduler: 'SchedulerProto', feedback: SchedulerFeedback) -> None:
        """ Register a scheduler by this callback
        """

        if feedback == SchedulerFeedback.source_subscribed:
            if self.__scheduler:
                raise ValueError('Unable to subscribe a second scheduler')
            self.__scheduler = scheduler
            self.__scheduler.callback(SchedulerProto.scheduled_task_completed, self.__record_completed_clbk)
        elif feedback == SchedulerFeedback.source_unsubscribed:
            if not self.__scheduler:
                raise ValueError('Unable to unsubscribe unknown scheduler')
            self.__scheduler.remove_callback(SchedulerProto.scheduled_task_completed, self.__record_completed_clbk)
            self.__scheduler = None
        else:
            raise ValueError('Unknown feedback spotted')

    def datalog(self) -> DatalogProto:
        return self.__datalog

    @classmethod
    def wait_for(cls, datalog: DatalogProto, api_id: str) -> typing.Optional[TaskResult]:

        def result_fn(entry: ChainedTaskLogEntry) -> bool:
            return entry.api_id == api_id and entry.state == ChainedTaskState.completed

        def complete_fn(entry: ChainedTaskLogEntry) -> bool:
            return entry.api_id == api_id and entry.state in (ChainedTaskState.completed, ChainedTaskState.finalized)

        result = datalog.find(result_fn, reverse=True)

        if result is None:
            with suppress(StopIteration):
                with SignalWaiter(datalog, DatalogProto.new_entry, value_matcher=complete_fn):
                    if datalog.find(complete_fn, reverse=True):
                        raise StopIteration('Stop to wait')

            result = datalog.find(result_fn, reverse=True)
        return result.result if result is not None else None

    def __record_group_id(self, api_id: str) -> str:
        """ Return identifier that will describe a group of tasks (in order to prevent a parallel run)
        """
        return f'{self.__source_uid}--{api_id}'

    def __skip_started(self, api_ids: typing.Set[str]) -> typing.Set[str]:
        """ Filter a list of api id and return only those that is not running at the moment
        """
        started = set()

        for log_entry in self.__datalog.iterate():
            if log_entry.api_id in api_ids:
                started.add(log_entry.api_id)

        return api_ids.difference(started)

    def __execution_row(self, api_id: str) -> None:
        """ Execute a task with api id and it's dependencies
        """
        assert(self.__queue_proxy.is_inside())

        if self.started_task(api_id) is not None:
            raise ValueError(f'The task "{api_id}" has been started already')

        task_cls = self.__registry.get(api_id)
        unprocessed_deps = [task_cls.dependencies()]
        execution_row = [api_id]

        while unprocessed_deps:
            next_deps = set()

            for dep in unprocessed_deps:
                if dep is None:
                    continue

                required = self.__skip_started(dep)

                if required.intersection(execution_row):
                    raise ValueError('Mutual dependencies found for a task')

                next_deps.update(required)
                for r in required:
                    execution_row.insert(0, r)

            unprocessed_deps = []
            for d in next_deps:
                task_cls = self.__registry.get(d)
                unprocessed_deps.append(task_cls.dependencies())

        for i in execution_row:
            self.__exec(i)

    def __wait_response(self, record: ScheduleRecordProto) -> typing.Optional[ReceivedSignal]:
        """ Start a record and wait for execution result. Result is a signal that has been received for a started
        task. It is one of:
          - SchedulerProto.scheduled_task_started
          - SchedulerProto.scheduled_task_dropped
          - SchedulerProto.scheduled_task_expired

        :param record: a record to start and track
        """
        assert(self.__queue_proxy.is_inside())

        if not self.__scheduler:
            raise ValueError('Scheduler has not registered yet')

        assert(record.postpone_policy() == ScheduledTaskPostponePolicy.drop)

        waiter = SignalWaiter(
            self.__scheduler, SchedulerProto.scheduled_task_started, value_matcher=lambda x: x == record
        )

        self.__scheduler.callback(SchedulerProto.scheduled_task_dropped, waiter)
        self.__scheduler.callback(SchedulerProto.scheduled_task_expired, waiter)

        self.emit(ScheduleSourceProto.task_scheduled, record)
        return waiter.wait()

    def __exec(self, api_id: str) -> None:
        """ Just execute a task with the specified api id
        """
        assert(self.__queue_proxy.is_inside())

        task_cls = self.__registry.get(api_id)
        task_uid = uuid.uuid4()
        record = ScheduleRecord(
            task_cls.create(self.__datalog, api_id, task_uid),
            self,
            simultaneous_runs=1,
            group_id=self.__record_group_id(api_id),
            postpone_policy=ScheduledTaskPostponePolicy.drop
        )

        await_result = self.__wait_response(record)
        if await_result is None or await_result.signal != SchedulerProto.scheduled_task_started:
            raise ValueError('Scheduler refused to start a record')
        else:
            self.__datalog.append(ChainedTaskLogEntry(api_id, task_uid, ChainedTaskState.started))

    def execute(self, api_id: str) -> None:
        """ Request to execute a task (and it's dependencies)
        """
        try:
            self.__queue_proxy.exec(functools.partial(self.__execution_row, api_id), blocking=True)
        except QueueCallbackException as e:
            raise e.__cause__  # type: ignore[misc]  # it's ok

    def started_task(self, api_id: str) -> typing.Optional[ChainedTaskLogEntry]:
        """ Return a last log record of the specified task
        """
        for log_entry in self.__datalog.iterate(reverse=True):
            if log_entry.api_id == api_id:
                return log_entry  # type: ignore[no-any-return]
        return None

    def start(self) -> None:
        """ Start this source
        """
        self.__queue_proxy.start()

    def stop(self) -> None:
        """ Stop this source
        """
        self.__queue_proxy.stop()
