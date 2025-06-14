# -*- coding: utf-8 -*-
# pyknic/lib/tasks/scheduler/scheduler.py
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

import functools
import typing
import weakref

from pyknic.lib.capability import iscapable
from pyknic.lib.signals.proto import Signal, SignalSourceProto
from pyknic.lib.signals.proxy import QueueCallbackException
from pyknic.lib.signals.extra import BoundedCallback, SignalResender, CallbacksHolder
from pyknic.lib.verify import verify_value

from pyknic.lib.tasks.proto import SchedulerProto, ScheduleSourceProto, TaskProto, SchedulerFeedback, TaskStopError

from pyknic.lib.tasks.scheduler.scheduler_executor import SchedulerExecutor


class Scheduler(SchedulerProto, TaskProto):
    """ The :class:`.SchedulerProto` class implementation
    """

    def __init__(
        self,
        threads_number: typing.Optional[int] = None,
        executor_cr_timeout: typing.Union[int, float, None] = None,
        thread_cr_timeout: typing.Union[int, float, None] = None,
        task_timeout: typing.Union[int, float, None] = None
    ):
        """ Create a new scheduler with an internal thread executor

        :param threads_number: same as the "threads_number" argument in :meth:`.ThreadExecutor.__init__`
        :param executor_cr_timeout: same as the "executor_cr_timeout" argument in :meth:`.ThreadExecutor.__init__`
        :param thread_cr_timeout: same as the "thread_cr_timeout" argument in :meth:`.ThreadExecutor.__init__`
        :param task_timeout: same as the "task_timeout" argument in :meth:`SchedulerExecutor.await_tasks`
        """
        SchedulerProto.__init__(self)
        TaskProto.__init__(self)

        self.__executor = SchedulerExecutor(threads_number, executor_cr_timeout, thread_cr_timeout)
        self.__task_timeout = task_timeout
        self.__holder = CallbacksHolder()
        self.__sources: weakref.WeakSet[ScheduleSourceProto] = weakref.WeakSet()  # protects from double subscriptions
        # TODO: think of removing this "self.__sources" -- it will make code cleaner

        self.__task_scheduled_clbk = BoundedCallback(self.__task_scheduled)

        def link_signals(source_signal: Signal, target_signal: Signal) -> None:
            self.__executor.callback(
                source_signal,
                self.__holder.keep_callback(
                    SignalResender(self, target_signal=target_signal),
                    self
                )
            )

        link_signals(SchedulerExecutor.scheduled_task_dropped, SchedulerProto.scheduled_task_dropped)
        link_signals(SchedulerExecutor.scheduled_task_postponed, SchedulerProto.scheduled_task_postponed)
        link_signals(SchedulerExecutor.scheduled_task_expired, SchedulerProto.scheduled_task_expired)
        link_signals(SchedulerExecutor.scheduled_task_started, SchedulerProto.scheduled_task_started)
        link_signals(SchedulerExecutor.scheduled_task_completed, SchedulerProto.scheduled_task_completed)

    def __task_scheduled(self, source: SignalSourceProto, signal: Signal, value: typing.Any) -> None:
        """ A task (value) has been scheduled so this callback is processing it

        :param source: source (ScheduleSourceProto) that generates an event
        :param signal: the "ScheduleSourceProto.task_scheduled" signal
        :param value: aka ScheduleRecordProto -- a record to execute
        """
        self.emit(SchedulerProto.task_scheduled, value)
        self.__executor.submit(value, blocking=False)

    def __subscribe(self, schedule_source: ScheduleSourceProto) -> None:
        """ Subscribe to a source

        :param schedule_source: a source to subscribe
        """
        assert(self.__executor.queue_proxy().is_inside())

        if schedule_source in self.__sources:
            raise ValueError('Source is subscribed already')

        if iscapable(schedule_source, ScheduleSourceProto.scheduler_feedback):
            schedule_source.scheduler_feedback(self, SchedulerFeedback.source_subscribed)
        schedule_source.callback(ScheduleSourceProto.task_scheduled, self.__task_scheduled_clbk)
        self.__sources.add(schedule_source)

    @verify_value(timeout=lambda x: x is None or x > 0)
    def subscribe(self, schedule_source: ScheduleSourceProto) -> None:
        """ Request a source subscription

        :param schedule_source: a source to subscribe
        """
        assert(not self.__executor.queue_proxy().is_inside())  # this prevents queue_proxy from self-blocking
        try:
            self.__executor.queue_proxy().exec(functools.partial(self.__subscribe, schedule_source), blocking=True)
        except QueueCallbackException as e:
            raise e.__cause__  # type: ignore[misc]  # it's ok

    def __unsubscribe(self, schedule_source: ScheduleSourceProto) -> None:
        """ Unsubscribe a source

        :param schedule_source: a source to unsubscribe
        """
        assert(self.__executor.queue_proxy().is_inside())

        try:
            self.__sources.remove(schedule_source)
        except KeyError:
            raise ValueError('Unknown source is requested to unsubscribe')

        if iscapable(schedule_source, ScheduleSourceProto.scheduler_feedback):
            schedule_source.scheduler_feedback(self, SchedulerFeedback.source_unsubscribed)

        schedule_source.remove_callback(ScheduleSourceProto.task_scheduled, self.__task_scheduled_clbk)

    @verify_value(timeout=lambda x: x is None or x > 0)
    def unsubscribe(self, schedule_source: ScheduleSourceProto) -> None:
        """ Request a source "unsubscription"

        :param schedule_source: a source to unsubscribe
        """
        assert(not self.__executor.queue_proxy().is_inside())  # this prevents queue_proxy from self-blocking
        try:
            self.__executor.queue_proxy().exec(functools.partial(self.__unsubscribe, schedule_source), blocking=True)
        except QueueCallbackException as e:
            raise e.__cause__  # type: ignore[misc]  # it's ok

    def start(self) -> None:
        """ Start a schedule
        """
        self.__executor.queue_proxy().start()

    def __unsubscribe_all(self) -> None:
        """ Unsubscribe all sources as a part of stopping procedure
        """
        assert(self.__executor.queue_proxy().is_inside())

        for source in self.__sources.copy():
            if source:
                self.__unsubscribe(source)

    def stop(self) -> None:
        """ Stop this schedule
        """
        assert(not self.__executor.queue_proxy().is_inside())  # this prevents queue_proxy from self-blocking
        self.__executor.queue_proxy().exec(self.__unsubscribe_all, blocking=True)
        self.__executor.cancel_postponed_tasks()
        self.__executor.stop_running_tasks()
        self.__executor.await_tasks(self.__task_timeout)

        pending_tasks = self.__executor.pending_tasks()
        running_tasks = self.__executor.running_tasks()

        pts = len(pending_tasks)
        rts = len(running_tasks)
        if (pts + rts) > 0:
            raise TaskStopError(
                f'Scheduler still has running/pending task(s) (running -- {rts}; pending -- {pts})'  # noqa: E702
            )

        self.__executor.queue_proxy().stop()
