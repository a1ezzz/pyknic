# -*- coding: utf-8 -*-
# pyknic/lib/tasks/scheduler/plain_sources.py
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

from pyknic.lib.tasks.proto import ScheduleSourceProto, ScheduleRecordProto


class InstantTaskSource(ScheduleSourceProto):
    """ The simplest source that sends record immediately
    """

    def schedule_record(self, record: ScheduleRecordProto) -> None:
        """ Send a record

        :param record: a record to emit
        """
        self.emit(ScheduleSourceProto.task_scheduled, record)
