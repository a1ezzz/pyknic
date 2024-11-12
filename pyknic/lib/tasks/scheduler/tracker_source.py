# -*- coding: utf-8 -*-
# pyknic/lib/tasks/scheduler/tracker_source.py
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

import threading
import typing

from pyknic.lib.signals.proto import SignalSourceProto, Signal
from pyknic.lib.signals.extra import BoundedCallback
from pyknic.lib.tasks.proto import ScheduleSourceProto, ScheduleRecordProto, SchedulerProto, SchedulerFeedback
from pyknic.lib.tasks.proto import ScheduledTaskPostponePolicy


class TaskTrackerSource(ScheduleSourceProto):
    """ This class helps to track a scheduled task. This source may be used by a single scheduler only
    """

    def __init__(self) -> None:
        """ Create a new tracker
        """
        ScheduleSourceProto.__init__(self)
        self.__scheduler: typing.Optional[SchedulerProto] = None

        self.__await_result_clbk = BoundedCallback(self.__await_result)

        self.__tracking_lock = threading.Lock()  # TODO: too much locking! think of refactoring
        self.__track_event = threading.Event()
        self.__track_result: typing.Optional[Signal] = None
        self.__tracked_record: typing.Optional[ScheduleRecordProto] = None

    def __await_result(self, source: SignalSourceProto, signal: Signal, value: typing.Any) -> None:
        """ This callback is used to track a result of a submitted record
        """
        with self.__tracking_lock:
            assert(self.__tracked_record is not None)

            if value is self.__tracked_record:
                assert(self.__track_result is None)

                self.__track_result = signal
                self.__track_event.set()

    def wait_response(self, record: ScheduleRecordProto) -> Signal:
        """ Start a record and wait for execution result. Result is a signal that has been received for a started
        task. It is one of:
          - SchedulerProto.scheduled_task_started
          - SchedulerProto.scheduled_task_dropped
          - SchedulerProto.scheduled_task_expired

        :param record: a record to start and track
        """

        if not self.__scheduler:
            raise ValueError('Scheduler has not registered yet')

        if record.postpone_policy() != ScheduledTaskPostponePolicy.drop:
            raise ValueError('A record must have the drop policy in order not to wait for a long time')

        with self.__tracking_lock:
            assert(self.__track_result is None)
            self.__tracked_record = record
            self.__track_result = None
            self.__track_event.clear()

        self.emit(ScheduleSourceProto.task_scheduled, record)
        self.__track_event.wait()
        result = self.__track_result

        with self.__tracking_lock:
            assert(self.__track_result is not None)
            self.__tracked_record = None
            self.__track_result = None
            self.__track_event.clear()

        return result

    def scheduler(self) -> typing.Optional[SchedulerProto]:
        """ Return a scheduler with which this source is registered
        """
        return self.__scheduler

    def scheduler_feedback(self, scheduler: 'SchedulerProto', feedback: SchedulerFeedback) -> None:
        """ The :meth:`.ScheduleSourceProto.scheduler_feedback` method implementation that tracks scheduler
        """
        if feedback == SchedulerFeedback.source_subscribed:
            if self.__scheduler:
                raise ValueError('Unable to subscribe a second scheduler')
            self.__scheduler = scheduler

            self.__scheduler.callback(SchedulerProto.scheduled_task_dropped, self.__await_result_clbk)
            self.__scheduler.callback(SchedulerProto.scheduled_task_expired, self.__await_result_clbk)
            self.__scheduler.callback(SchedulerProto.scheduled_task_started, self.__await_result_clbk)
            return

        elif feedback == SchedulerFeedback.source_unsubscribed:
            if not self.__scheduler:
                raise ValueError('Unable to unsubscribe unknown scheduler')

            self.__scheduler.remove_callback(SchedulerProto.scheduled_task_dropped, self.__await_result_clbk)
            self.__scheduler.remove_callback(SchedulerProto.scheduled_task_expired, self.__await_result_clbk)
            self.__scheduler.remove_callback(SchedulerProto.scheduled_task_started, self.__await_result_clbk)

            self.__scheduler = None
            return

        raise ValueError('Unknown feedback spotted')
