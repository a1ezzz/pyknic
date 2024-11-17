# -*- coding: utf-8 -*-
# pyknic/lib/tasks/scheduler/record.py
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

from pyknic.lib.tasks.proto import ScheduleRecordProto, TaskProto, ScheduledTaskPostponePolicy, ScheduleSourceProto


class ScheduleRecord(ScheduleRecordProto):
    """ The :class:`.ScheduleRecordProto` implementation. Implementation is pretty straightforward
    """

    def __init__(
        self,
        task: TaskProto,
        source: ScheduleSourceProto,
        group_id: typing.Optional[str] = None,
        ttl: typing.Optional[typing.Union[int, float]] = None,
        simultaneous_runs: typing.Optional[int] = None,
        postpone_policy: typing.Optional[ScheduledTaskPostponePolicy] = None
    ):
        """ Create a new record

        :param task: a task to execute
        :param group_id: record's group id. Please read :meth:`.ScheduleRecordProto.group_id`
        :param ttl: record's ttl
        :param simultaneous_runs: how many records with the same group_id should be running at the moment
        :param postpone_policy: what should be done if this record will be postponed
        """
        self.__task = task
        self.__source = source
        self.__group_id = group_id
        self.__ttl = ttl
        self.__simultaneous_runs = simultaneous_runs if simultaneous_runs is not None else 0
        self.__postpone_policy = postpone_policy if postpone_policy else ScheduledTaskPostponePolicy.wait

    def task(self) -> TaskProto:
        """ The :meth:`.ScheduleRecordProto.task` method implementation
        """
        return self.__task

    def source(self) -> 'ScheduleSourceProto':
        """ The :meth:`.ScheduleRecordProto.source` method implementation
        """
        return self.__source

    def group_id(self) -> typing.Optional[str]:
        """ The :meth:`.ScheduleRecordProto.group_id` method implementation
        """
        return self.__group_id

    def ttl(self) -> typing.Union[int, float, None]:
        """ The :meth:`.ScheduleRecordProto.ttl` method implementation
        """
        return self.__ttl

    def simultaneous_runs(self) -> int:
        """ The :meth:`.ScheduleRecordProto.simultaneous_policy` method implementation
        """
        return self.__simultaneous_runs

    def postpone_policy(self) -> ScheduledTaskPostponePolicy:
        """ The :meth:`.ScheduleRecordProto.postpone_policy` method implementation
        """
        return self.__postpone_policy
