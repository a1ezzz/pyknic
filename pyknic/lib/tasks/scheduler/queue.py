# -*- coding: utf-8 -*-
# pyknic/lib/tasks/scheduler/queue.py
#
# Copyright (C) 2017-2024 the pyknic authors and contributors
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

import typing

from datetime import datetime, timezone

from pyknic.lib.signals.proto import Signal
from pyknic.lib.signals.source import SignalSource

from pyknic.lib.tasks.proto import ScheduleRecordProto, ScheduledTaskPostponePolicy


class SchedulerQueue(SignalSource):
    """ This class is a part of :class:`.SchedulerProto` implementation. This class allows to postpone records.

    :note: Methods in this class are not thread safe!
    """

    task_dropped = Signal(ScheduleRecordProto)    # a scheduled task dropped and would not start
    task_postponed = Signal(ScheduleRecordProto)  # a scheduled task postponed and will start later
    task_expired = Signal(ScheduleRecordProto)    # a scheduled task dropped because of expired ttl

    def __init__(self) -> None:
        """ Create a new queue with postpone records
        """
        SignalSource.__init__(self)
        self.__postponed_records: typing.List[ScheduleRecordProto] = []

    def __len__(self) -> int:
        """ Return number of postponed tasks
        """
        return len(self.__postponed_records)

    def __drop_all(self, group_id: str) -> None:
        """ Drop from a queue all record with the specified group_id

        :param group_id: id of a group which records should be dropped
        """
        dropped_records = 0
        for i in range(len(self.__postponed_records)):
            check_record = self.__postponed_records[i - dropped_records]
            if check_record.group_id() == group_id:
                self.__postponed_records.pop(i - dropped_records)
                dropped_records += 1
                self.emit(self.task_dropped, check_record)

    def __keep_first(self, group_id: str) -> bool:
        """ Try to keep the earliest record of the same group. Other records of the same group will be dropped

        :param group_id: id of a group which records should be dropped (all but the earliest)

        :return: return True if the earliest record was found and return False otherwise
        """
        first_found = False
        dropped_records = 0
        for i in range(len(self.__postponed_records)):
            check_record = self.__postponed_records[i - dropped_records]
            if check_record.group_id() == group_id:
                if first_found:
                    self.__postponed_records.pop(i - dropped_records)
                    self.emit(self.task_dropped, check_record)
                    dropped_records += 1
                else:
                    first_found = True
        return first_found

    def postpone(self, record: ScheduleRecordProto) -> None:
        """ Postpone a record (or drop it because of policy and/or ttl)

        :param record: record to postpone
        """
        ttl = record.ttl()
        group_id = record.group_id()
        postpone_policy = record.postpone_policy()

        if postpone_policy == ScheduledTaskPostponePolicy.drop:
            self.emit(self.task_dropped, record)
            return

        if ttl is not None and ttl < datetime.now(timezone.utc).timestamp():
            self.emit(self.task_expired, record)
            return

        if postpone_policy == ScheduledTaskPostponePolicy.wait or group_id is None:
            self.__postponed_records.append(record)
            self.emit(self.task_postponed, record)
            return

        if postpone_policy == ScheduledTaskPostponePolicy.keep_last:
            self.__drop_all(group_id)
            self.__postponed_records.append(record)
            self.emit(self.task_postponed, record)
            return

        if postpone_policy == ScheduledTaskPostponePolicy.keep_first:
            if not self.__keep_first(group_id):
                self.__postponed_records.append(record)
                self.emit(self.task_postponed, record)
            else:
                self.emit(self.task_dropped, record)

    def next_record(
        self,
        filter_fn: typing.Optional[typing.Callable[[ScheduleRecordProto], bool]] = None
    ) -> typing.Optional[ScheduleRecordProto]:
        """ Get record from a queue to be executed next. The earliest records win, but not always

        :param filter_fn: check a record with this function. If record is suitable then this function should return
        True or return False otherwise

        :return: return a record that should be executed next or return None if no suitable record is found
        """

        utc_now = datetime.now(timezone.utc).timestamp()
        dropped_records = 0

        for i in range(len(self.__postponed_records)):
            record = self.__postponed_records[i - dropped_records]

            ttl = record.ttl()
            if ttl is not None and ttl < utc_now:
                self.__postponed_records.pop(i - dropped_records)
                self.emit(self.task_expired, record)
                dropped_records += 1
                continue

            if filter_fn and not filter_fn(record):
                continue

            self.__postponed_records.pop(i - dropped_records)
            return record
        return None
