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

from pyknic.lib.signals.proto import Signal, SignalSourceProto, SignalCallbackType
from pyknic.lib.signals.extra import BoundedCallback, SignalResender
from pyknic.lib.verify import verify_value

from pyknic.lib.tasks.proto import SchedulerProto, ScheduleSourceProto, TaskProto

from pyknic.lib.tasks.scheduler.scheduler_executor import SchedulerExecutor


class Scheduler(SchedulerProto, TaskProto):
    """ The :class:`.SchedulerProto` class implementation
    """

    def __init__(
        self,
        threads_number: typing.Optional[int] = None,
        executor_cr_timeout: typing.Union[int, float, None] = None,
        thread_cr_timeout: typing.Union[int, float, None] = None
    ):
        """ Create a new scheduler with an internal thread executor

        :param threads_number: same as the "threads_number" argument in :method:`.ThreadExecutor.__init__`
        :param executor_cr_timeout: same as the "executor_cr_timeout" argument in :method:`.ThreadExecutor.__init__`
        :param thread_cr_timeout: same as the "thread_cr_timeout" argument in :method:`.ThreadExecutor.__init__`
        """
        SchedulerProto.__init__(self)
        TaskProto.__init__(self)

        self.__executor = SchedulerExecutor(threads_number, executor_cr_timeout, thread_cr_timeout)
        self.__sources_callbacks: weakref.WeakKeyDictionary[ScheduleSourceProto, SignalCallbackType] = \
            weakref.WeakKeyDictionary()

        self.__task_scheduled_clbk = BoundedCallback(self.__task_scheduled)

        self.__resenders: typing.Set[SignalResender] = set()

        def link_signals(source_signal: Signal, target_signal: Signal) -> None:
            nonlocal self
            callback = SignalResender(self, target_signal=target_signal)
            self.__resenders.add(callback)
            self.__executor.callback(source_signal, callback)

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
        assert(self.__executor.queue_proxy().is_inside())

        self.emit(SchedulerProto.task_scheduled, value)
        self.__executor.submit(value, blocking=False)

    def __subscribe(self, schedule_source: ScheduleSourceProto) -> None:
        """ Subscribe to a source

        :param schedule_source: a source to subscribe
        """
        assert(self.__executor.queue_proxy().is_inside())

        if schedule_source in self.__sources_callbacks:
            raise ValueError('Source is subscribed already')

        callback = self.__executor.queue_proxy().proxy(self.__task_scheduled_clbk)
        self.__sources_callbacks[schedule_source] = callback
        schedule_source.callback(ScheduleSourceProto.task_scheduled, callback)

    @verify_value(timeout=lambda x: x is None or x > 0)
    def subscribe(self, schedule_source: ScheduleSourceProto) -> None:
        """ Request a source subscription

        :param schedule_source: a source to subscribe
        """
        self.__executor.queue_proxy().exec(functools.partial(self.__subscribe, schedule_source), blocking=True)

    def __unsubscribe(self, schedule_source: ScheduleSourceProto) -> None:
        """ Unsubscribe a source

        :param schedule_source: a source to unsubscribe
        """
        assert(self.__executor.queue_proxy().is_inside())

        try:
            callback = self.__sources_callbacks.pop(schedule_source)
        except KeyError:
            raise ValueError('Unknown source is requested to unsubscribe')

        schedule_source.remove_callback(ScheduleSourceProto.task_scheduled, callback)

    @verify_value(timeout=lambda x: x is None or x > 0)
    def unsubscribe(self, schedule_source: ScheduleSourceProto) -> None:
        """ Request a source "unsubscription"

        :param schedule_source: a source to unsubscribe
        """
        self.__executor.queue_proxy().exec(functools.partial(self.__unsubscribe, schedule_source), blocking=True)

    def start(self) -> None:
        """ Start a schedule
        """
        self.__executor.queue_proxy().start()

    def __unsubscribe_all(self) -> None:
        """ Unsubscribe all sources as a part of stopping procedure
        """
        assert(self.__executor.queue_proxy().is_inside())

        for source, callback in self.__sources_callbacks.items():
            if source:
                source.remove_callback(ScheduleSourceProto.task_scheduled, callback)
        self.__sources_callbacks.clear()

    def stop(self) -> None:
        """ Stop this schedule
        """
        self.__executor.queue_proxy().exec(self.__unsubscribe_all, blocking=True)
        self.__executor.cancel_postponed_tasks()
        # TODO: request current running tasks to stop
        self.__executor.await_tasks()
        self.__executor.queue_proxy().stop()
