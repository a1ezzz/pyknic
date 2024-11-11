# -*- coding: utf-8 -*-
# pyknic/lib/tasks/proto.py
#
# Copyright (C) 2016-2024 the pyknic authors and contributors
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

import enum
import typing

from abc import ABCMeta, abstractmethod
from dataclasses import dataclass

from pyknic.lib.x_mansion import CapabilitiesAndSignals
from pyknic.lib.signals.proto import Signal
from pyknic.lib.signals.source import SignalSource
from pyknic.lib.capability import capability


class TaskStartError(Exception):
    """ This exception is raised when there is an error in starting a task
    """
    pass


class TaskStopError(Exception):
    """ This exception is raised when there is an error in stopping a task
    """
    pass


class NoSuchTaskError(Exception):
    """ This exception is raised when there is no requested task (it may be a request to start unknown task or
    request to stop already stopped task)
    """
    pass


@dataclass
class TaskResult:
    """ This class is used along with a completion signal defining a result of a completed task. In order to check
    whether a task was completed successfully the 'exception' property should be checked

    :note: the 'result' property may be not the same as the result from the original :meth:`TaskProto.start`
    method call
    """
    result: typing.Any = None                         # a result of completed record (if any)
    exception: typing.Optional[BaseException] = None  # an exception raised within a task (if any)


class TaskProto(CapabilitiesAndSignals):
    """ Basic task prototype. Derived classes must implement the only thing - :meth:`TaskProto.start`
    """

    task_started = Signal()              # a task started
    task_completed = Signal(TaskResult)  # a task completed

    @abstractmethod
    def start(self) -> None:
        """ Start a task
        """
        raise NotImplementedError('This method is abstract')

    @capability
    def stop(self) -> None:
        """ Try to stop this task gracefully.

        :raise NotImplementedError: if this task can not be stopped
        """
        raise NotImplementedError('The "stop" method is not supported')

    @capability
    def terminate(self) -> None:
        """ Try to stop this task at all costs

        :raise NotImplementedError: if this task can not be terminated
        """
        raise NotImplementedError('The "terminate" method is not supported')


@enum.unique
class ScheduledTaskPostponePolicy(enum.Enum):
    """ This is a policy that describes what should be done with a task if a scheduler won't be able to run
    it (like if the scheduler's limit of running tasks is reached).
    """
    wait = enum.auto()        # will postpone the task to execute it later
    drop = enum.auto()        # drop this task if it can't be executed at the moment
    keep_first = enum.auto()  # if there are postponed tasks, then drop this task
    keep_last = enum.auto()   # if there are postponed tasks, drop them and keep this task


class ScheduleRecordProto(metaclass=ABCMeta):
    """ This class describes a single request that scheduler (:class:`.SchedulerProto`) should process
    (should start). It has a :class:`.ScheduledTaskProto` task to be started and postpone policy
    (:class:`.TaskPostponePolicy`)

    Postpone policy is a recommendation for a scheduler and a scheduler can omit it if (for example) a scheduler queue
    is full. 'ScheduledTaskPostponePolicy.keep_first' and 'ScheduledTaskPostponePolicy.keep_last' postpone policies
    (so as simultaneous policy) will be applied to this task and to tasks with the same group id (if it was set).
    """

    @abstractmethod
    def task(self) -> TaskProto:
        """ Return a task that should be started
        """
        raise NotImplementedError('This method is abstract')

    def group_id(self) -> typing.Optional[str]:
        """ Return group id that unite records (in order 'ScheduledTaskPostponePolicy.keep_first' and
        'ScheduledTaskPostponePolicy.keep_last' to work; :meth:`.ScheduleRecordProto.simultaneous_policy` depends on
        this id also)

        :return: group id or None if this record is standalone
        """
        return None

    def ttl(self) -> typing.Union[int, float, None]:
        """ Return unix time when this record should be discarded

        :return: unix time in seconds or None if this record can not be expired. A timestamp must be return in UTC
        """
        return None

    def simultaneous_runs(self) -> int:
        """ Return how many records with the same group id may be run simultaneously. If non-positive value is return
        then there is no restrictions
        """
        return 0

    def postpone_policy(self) -> ScheduledTaskPostponePolicy:
        """ Return a postpone policy
        """
        return ScheduledTaskPostponePolicy.wait


@enum.unique
class SchedulerFeedback(enum.Enum):
    """ This enum flag is used along with the :meth:`.SchedulerProto.scheduler_feedback` method
    """
    source_subscribed = enum.auto()    # this flag shows that source in subscribed
    source_unsubscribed = enum.auto()  # this flag shows that source in unsubscribed


class ScheduleSourceProto(CapabilitiesAndSignals):
    """ This class may generate :class:`.ScheduleRecordProto` requests for a scheduler (:class:`.SchedulerProto`).
    This class decides what tasks and when should be run. When a time is come then this source emits
    a ScheduleSourceProto.task_scheduled signal
    """

    task_scheduled = Signal(ScheduleRecordProto)   # a new task should be started

    @capability
    def scheduler_feedback(self, scheduler: 'SchedulerProto', feedback: SchedulerFeedback) -> None:
        """ This method is used with the :class:`.SchedulerProto` class to notify that this source is used
        by the specified scheduler

        :param scheduler: scheduler that notifies
        :param feedback: scheduler's feedback event
        """
        raise NotImplementedError('The "stop" method is not supported')


# noinspection PyAbstractClass
class SchedulerProto(SignalSource):
    """ Represent a scheduler. A class that is able to execute tasks (:class:`.ScheduleRecordProto`) scheduled
    by sources (:class:`.ScheduleSourceProto`). This class tracks state of tasks that are running
    """

    task_scheduled = Signal(ScheduleRecordProto)            # a new task received from some source
    scheduled_task_dropped = Signal(ScheduleRecordProto)    # a scheduled task dropped and would not start
    scheduled_task_postponed = Signal(ScheduleRecordProto)  # a scheduled task dropped and will start later
    scheduled_task_expired = Signal(ScheduleRecordProto)    # a scheduled task dropped because of expired ttl
    scheduled_task_started = Signal(ScheduleRecordProto)    # a scheduled task started
    scheduled_task_completed = Signal(ScheduleRecordProto)  # a scheduled task completed

    @abstractmethod
    def subscribe(self, schedule_source: ScheduleSourceProto) -> None:
        """ Subscribe this scheduler to a specified source in order to start tasks from it

        :param schedule_source: source of records that should be subscribed
        """
        raise NotImplementedError('This method is abstract')

    @abstractmethod
    def unsubscribe(self, schedule_source: ScheduleSourceProto) -> None:
        """ Unsubscribe this scheduler from a specified sources and do process tasks from it

        :param schedule_source: source of records to unsubscribe from
        """
        raise NotImplementedError('This method is abstract')


class TaskExecutorProto(metaclass=ABCMeta):
    """ This is a class that executes tasks
    """

    @abstractmethod
    def submit_task(self, task: TaskProto) -> bool:
        """ Try to execute a task and return True if the task will be/or is already executed (return False otherwise)

        :param task: a task to execute
        """
        raise NotImplementedError('This method is abstract')

    @abstractmethod
    def complete_task(self, task: TaskProto) -> bool:
        """ Should be called for every successfully submitted task in order to finalize it

        :param task: task to finalize
        :return: True if a task is finalized successfully or return False otherwise
        """
        raise NotImplementedError('This method is abstract')

    @abstractmethod
    def wait_task(
        self,
        task: TaskProto,
        timeout: typing.Union[int, float, None] = None
    ) -> bool:
        """ Wait for a task completion

        :param task: a successfully submitted task to wait
        :param timeout: defines whether this function should be called in a blocking manner (and for how long)
        If value is None then this function will wait forever, if value is negative or zero, then this function will
        poll current state, otherwise -- number of seconds to wait for

        :return: return True if the task is completed and return False otherwise
        """
        raise NotImplementedError('This method is abstract')

    @abstractmethod
    def tasks(self) -> typing.Generator[TaskProto, None, None]:
        """ Return generator that yields currently running tasks
        """
        raise NotImplementedError('This method is abstract')
