# -*- coding: utf-8 -*-
# pyknic/lib/tasks/scheduler/scheduler_executor.py
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

import enum
import functools
import typing

from dataclasses import dataclass
from datetime import datetime, timezone

from pyknic.lib.capability import iscapable
from pyknic.lib.tasks.proto import ScheduleRecordProto, TaskProto, ScheduledTaskPostponePolicy, NoSuchTaskError
from pyknic.lib.tasks.scheduler.queue import SchedulerQueue
from pyknic.lib.signals.proto import SignalSourceProto, Signal
from pyknic.lib.signals.extra import BoundedCallback, SignalResender, CallbacksHolder
from pyknic.lib.signals.proxy import QueueProxy, QueueCallbackException
from pyknic.lib.signals.source import SignalSource
from pyknic.lib.tasks.thread_executor import ThreadExecutor, NoFreeSlotError


class SchedulerExecutor(SignalSource):
    """ This class simplifies SchedulerProto implementation by implementing an execution/postponing process
    as a single point (single source of truth)

    Because it may (and will) be addressed in concurrency manner, it is crucial to follow the steps in order to
    stop a scheduler correctly and in a consistent way. So there they are:
      1. Unsubscribe all the sources in order to stop new record processing.
      The `meth:.SchedulerProto.unsubscribe` method will help
      2. Drop all the postponed tasks. This will do the :meth:`.SchedulerExecutor.cancel_postponed_tasks` method
      3. Request running tasks to stop (the :meth:`.SchedulerExecutor.stop_running_tasks` will do)
      4. Wait for running tasks to complete, join threads and execute all the callbacks that are stored
      (the :meth:`.SchedulerExecutor.await_tasks` method is responsible for this)
    """

    scheduled_task_dropped = Signal(ScheduleRecordProto)    # a scheduled task dropped and would not start
    scheduled_task_postponed = Signal(ScheduleRecordProto)  # a scheduled task postponed and will start later
    scheduled_task_expired = Signal(ScheduleRecordProto)    # a scheduled task dropped because of expired ttl
    scheduled_task_started = Signal(ScheduleRecordProto)    # a scheduled task started
    scheduled_task_completed = Signal(ScheduleRecordProto)  # a scheduled task completed

    @enum.unique
    class TaskState(enum.Enum):
        """ This class shows the state of a task/record
        """
        submitted = enum.auto()  # task is submitted, but decision is not made yet
        pending = enum.auto()    # task is not executed at the moment but waits for it
        started = enum.auto()    # task is started

    @dataclass
    class TaskDescriptor:
        """ Describes a submitted task
        """
        record: ScheduleRecordProto           # record that submitted a task
        state: 'SchedulerExecutor.TaskState'  # state of a task

    def __init__(
        self,
        threads_number: typing.Optional[int] = None,
        executor_cr_timeout: typing.Union[int, float, None] = None,
        thread_cr_timeout: typing.Union[int, float, None] = None
    ):
        """ Create an executor. This also creates an internal queue (:class:`.QueueProxy`) for callbacks processing and
        an internal thread executor (:class:`.ThreadExecutor`) to run tasks

        :param threads_number: same as the "threads_number" argument in :method:`.ThreadExecutor.__init__`
        :param executor_cr_timeout: same as the "executor_cr_timeout" argument in :method:`.ThreadExecutor.__init__`
        :param thread_cr_timeout: same as the "thread_cr_timeout" argument in :method:`.ThreadExecutor.__init__`
        """
        SignalSource.__init__(self)
        self.__proxy = QueueProxy()
        self.__scheduler_queue = SchedulerQueue()
        self.__thread_executor = ThreadExecutor(threads_number, executor_cr_timeout, thread_cr_timeout)

        self.__tasks: typing.Dict[TaskProto, 'SchedulerExecutor.TaskDescriptor'] = dict()

        self.__holder = CallbacksHolder()

        self.__thread_executor.callback(
            ThreadExecutor.task_completed,
            self.__proxy.proxy(
                self.__holder.keep_callback(
                    BoundedCallback(self.__task_completed),
                    self
                )
            )
        )

        self.__scheduler_queue.callback(
            SchedulerQueue.task_expired,
            self.__holder.keep_callback(
                SignalResender(self, target_signal=SchedulerExecutor.scheduled_task_expired),
                self
            )
        )

        self.__scheduler_queue.callback(
            SchedulerQueue.task_dropped,
            self.__holder.keep_callback(
                SignalResender(self, target_signal=SchedulerExecutor.scheduled_task_dropped),
                self
            )
        )

    def __task_completed(self, source: SignalSourceProto, signal: Signal, value: typing.Any) -> None:
        """ This callback is executed when a task is about to finish

        :param source: the :class:`.ThreadExecutor` instance
        :param signal: it will be the "ThreadExecutor.task_completed" signal
        :param value: it will be a task (:class:`.TaskProto`) that about to complete
        """
        assert(self.__proxy.is_inside())

        self.__thread_executor.wait_task(value)
        self.__thread_executor.complete_task(value)
        descriptor = self.__tasks.pop(value)
        self.emit(SchedulerExecutor.scheduled_task_completed, descriptor.record)
        self.__proxy.exec(self.__run_postponed_tasks)

    def __run_postponed_tasks(self) -> None:
        """ This callback is for postponed tasks execution
        """
        assert(self.__proxy.is_inside())

        while True:
            try:
                with self.__thread_executor.executor_context() as c:
                    record = self.__scheduler_queue.next_record(self.__filter_record)
                    if record is None:
                        break
                    self.__exec_task(record, c)
            except NoFreeSlotError:
                break

    def __exec_task(self, record: ScheduleRecordProto, context: ThreadExecutor.Context) -> None:
        """ This callback executes a record (a task)

        :param record: a record to execute
        :param context: context with which a slot for execution has been allocated
        """
        assert(self.__proxy.is_inside())

        task = record.task()
        self.__tasks[task].state = SchedulerExecutor.TaskState.started
        context.submit_task(task)
        self.emit(SchedulerExecutor.scheduled_task_started, record)

    def __postpone(self, record: ScheduleRecordProto) -> None:
        """ This callback postpones or drops a record

        :param record: a record to postpone
        """
        assert(self.__proxy.is_inside())

        if record.postpone_policy() == ScheduledTaskPostponePolicy.drop:
            self.__tasks.pop(record.task())
            self.emit(SchedulerExecutor.scheduled_task_dropped, record)
            return

        self.__tasks[record.task()].state = SchedulerExecutor.TaskState.pending
        self.emit(SchedulerExecutor.scheduled_task_postponed, record)
        self.__scheduler_queue.postpone(record)

    def __submit(self, record: ScheduleRecordProto) -> None:
        """ This callback processes a submitted task and tries to execute it

        :param record: a record that should be executed
        """
        assert(self.__proxy.is_inside())

        ttl = record.ttl()
        if ttl is not None and ttl < datetime.now(timezone.utc).timestamp():
            self.emit(SchedulerExecutor.scheduled_task_expired, record)
            return

        if record.task() in self.__tasks:
            raise ValueError('A submitted task is registered already')

        self.__tasks[record.task()] = SchedulerExecutor.TaskDescriptor(
            record, SchedulerExecutor.TaskState.submitted
        )

        if not self.__filter_record(record):
            self.__postpone(record)
            return

        try:
            with self.__thread_executor.executor_context() as c:
                self.__exec_task(record, c)
        except NoFreeSlotError:
            self.__postpone(record)

    def submit(self, record: ScheduleRecordProto, blocking: bool = False) -> None:
        """ Try to execute a record or try to postpone it

        :param record: a record to run
        :param blocking: whether we should wait for result or not (a queue thread may be deadlocked because
        of the True value)
        """
        try:
            self.__proxy.exec(functools.partial(self.__submit, record), blocking=blocking)
        except QueueCallbackException as e:
            raise e.__cause__  # type: ignore[misc]  # it's ok

    def queue_proxy(self) -> QueueProxy:
        """ Return internal proxy
        """
        return self.__proxy

    def __has_tasks(self) -> bool:
        """ Check are there tasks to execute

        :return: True if there are tasks to execute and False otherwise
        """
        return len(self.__scheduler_queue) > 0 or any(self.__thread_executor.tasks())

    def await_tasks(self, task_timeout: typing.Union[int, float, None] = None) -> None:
        """ Wait for tasks to finish

        :param task_timeout: a timeout for each task to complete
        """
        has_tasks = self.__proxy.exec(self.__has_tasks, blocking=True)
        while has_tasks:
            for task in self.__thread_executor.tasks():
                try:
                    if not self.__thread_executor.wait_task(task, timeout=task_timeout):
                        raise TimeoutError('Unable to wait for a task in a time')
                except NoSuchTaskError:
                    # there may be a slight race condition between thread_executor.tasks() and wait_task calls
                    pass

            self.__proxy.exec(self.__run_postponed_tasks, blocking=True)
            has_tasks = self.__proxy.exec(self.__has_tasks, blocking=True)

    def __filter_record(self, record: ScheduleRecordProto) -> bool:
        """ A filter for the :meth:`.SchedulerQueue.next_record` method that checks the "simultaneous_runs" option
        """
        group_id = record.group_id()
        simultaneous_runs = record.simultaneous_runs()

        def sim_runs(x: SchedulerExecutor.TaskDescriptor) -> int:
            return 1 if (x.state == SchedulerExecutor.TaskState.started and x.record.group_id() == group_id) else 0

        if group_id is not None and simultaneous_runs > 0:
            group_count = sum(map(sim_runs, self.__tasks.values()))
            if group_count >= simultaneous_runs:
                return False

        return True

    def __cancel_postponed_tasks(self) -> None:
        """ Cancel all the pending tasks
        """
        assert (self.__proxy.is_inside())

        next_record = self.__scheduler_queue.next_record()
        while next_record:
            self.__tasks.pop(next_record.task())
            self.emit(SchedulerExecutor.scheduled_task_dropped, next_record)
            next_record = self.__scheduler_queue.next_record()

    def cancel_postponed_tasks(self) -> None:
        """ Request to cancel all the pending tasks
        """
        self.__proxy.exec(self.__cancel_postponed_tasks, blocking=True)

    def __stop_running_tasks(self) -> None:
        """ Cancel all the pending tasks
        """
        assert(self.__proxy.is_inside())

        for task in self.__tasks:
            if iscapable(task, TaskProto.stop):
                task.stop()
            elif iscapable(task, TaskProto.terminate):
                task.terminate()

    def stop_running_tasks(self) -> None:
        """ Request to cancel all the running tasks
        """
        self.__proxy.exec(self.__stop_running_tasks, blocking=True)

    def __tasks_filter(
        self,
        filter_fn: typing.Callable[['SchedulerExecutor.TaskDescriptor'], bool]
    ) -> typing.Tuple[TaskProto, ...]:
        """ This method returns tasks which descriptors is suitable

        :param filter_fn: filter function that checks descriptors, this function must return True
        for every suitable task
        """
        assert(self.__proxy.is_inside())

        return tuple((x for x, y in self.__tasks.items() if filter_fn(y)))

    def running_tasks(self) -> typing.Tuple[TaskProto, ...]:
        """ Return tasks that are running at the moment
        """
        return self.__proxy.exec(  # type: ignore[no-any-return]
            functools.partial(
                self.__tasks_filter,
                lambda x: x.state == SchedulerExecutor.TaskState.started
            ),
            blocking=True
        )

    def pending_tasks(self) -> typing.Tuple[TaskProto, ...]:
        """ Return tasks that are waiting for execution
        """
        return self.__proxy.exec(  # type: ignore[no-any-return]
            functools.partial(
                self.__tasks_filter,
                lambda x: x.state != SchedulerExecutor.TaskState.started
            ),
            blocking=True
        )
