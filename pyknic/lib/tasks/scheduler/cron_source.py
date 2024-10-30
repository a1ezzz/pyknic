# -*- coding: utf-8 -*-
# pyknic/lib/tasks/scheduler/cron_source.py
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

import calendar
import datetime
import heapq
import typing

from pyknic.lib.verify import verify_value
from pyknic.lib.signals.proto import Signal

from pyknic.lib.tasks.proto import ScheduleSourceProto, ScheduleRecordProto


def cron_token_validator(value_min: int, value_max: int) -> typing.Callable[[int], bool]:
    """ Return function that checks integer value -- that this value resides between lower and upper bounds

    :param value_min: minimum acceptable value
    :param value_max: maximum acceptable value
    """
    def validator(value: int) -> bool:
        return value is None or (value_min <= value <= value_max)
    return validator


class CronSchedule:
    """ This class defines cron-a-like schedule
    """

    __calendar__ = {1: 31, 2: 29, 3: 31, 4: 30, 5: 31, 6: 30, 7: 31, 8: 31, 9: 30, 10: 31, 11: 30, 12: 31}

    @verify_value(minute=cron_token_validator(0, 59))
    @verify_value(hour=cron_token_validator(0, 23))
    @verify_value(day_of_month=cron_token_validator(1, 31))
    @verify_value(day_of_week=cron_token_validator(1, 7))
    @verify_value(month=cron_token_validator(1, 12))
    def __init__(
        self,
        minute: typing.Optional[int] = None,
        hour: typing.Optional[int] = None,
        day_of_month: typing.Optional[int] = None,
        day_of_week: typing.Optional[int] = None,
        month: typing.Optional[int] = None
    ):
        """ Create a new schedule

        :param minute: a minute of a schedule (None means every minute)
        :param hour: a hour of a schedule (None means every hour)
        :param day_of_month: a day of a month of a schedule (None means every day)
        :param day_of_week: a day of a week of a schedule (None means every day of week)
        :param month: a month of a schedule (None means every month)
        """

        if month is not None and day_of_month is not None and day_of_month > CronSchedule.__calendar__[month]:
            raise ValueError('Invalid day and month combination')

        self.__minute = minute
        self.__hour = hour
        self.__day_of_month = day_of_month
        self.__day_of_week = day_of_week
        self.__month = month

    def minute(self) -> typing.Optional[int]:
        """ Return scheduler's minute setting
        """
        return self.__minute

    def hour(self) -> typing.Optional[int]:
        """ Return scheduler's hour setting
        """
        return self.__hour

    def day_of_month(self) -> typing.Optional[int]:
        """ Return scheduler's day of month setting
        """
        return self.__day_of_month

    def day_of_week(self) -> typing.Optional[int]:
        """ Return scheduler's day of week setting
        """
        return self.__day_of_week

    def month(self) -> typing.Optional[int]:
        """ Return scheduler's month setting
        """
        return self.__month

    @verify_value(start_datetime=lambda x: x.tzinfo is not None)
    def iterate(self, start_datetime: datetime.datetime) -> typing.Generator[datetime.datetime, None, None]:
        """ Return generator that yields datetime at which something should happen
        """

        def is_start_date(y: int, m: int, d: int) -> bool:
            return y == start_datetime.year and m == start_datetime.month and d == start_datetime.day

        for year, month in self.__month_iterator(start_datetime.year, start_datetime.month):

            current_day = 1
            if year == start_datetime.year and month == start_datetime.month:
                current_day = start_datetime.day  # reset day since a new year/month iteration

            for day in self.__day_iterator(year, month, current_day):

                current_hour = 0
                if is_start_date(year, month, day):
                    current_hour = start_datetime.hour

                for hour in self.__time_iterator(current_hour, 23, self.hour()):
                    current_minute = 0
                    if is_start_date(year, month, day) and hour == start_datetime.hour:
                        current_minute = start_datetime.minute
                    for minute in self.__time_iterator(current_minute, 59, self.minute()):
                        yield datetime.datetime(year, month, day, hour, minute, tzinfo=start_datetime.tzinfo)

    def __month_iterator(
        self, start_year: int, start_month: int
    ) -> typing.Generator[typing.Tuple[int, int], None, None]:
        """ Internal generator that iterates over months
        """
        iter_month = self.month()

        if iter_month is not None:
            if start_month > iter_month:
                start_year += 1
            start_month = iter_month

        next_year = start_year
        next_month = start_month

        while next_year <= datetime.MAXYEAR:
            yield next_year, next_month

            if iter_month is not None:
                next_year += 1
            elif next_month < 12:
                next_month += 1
            else:
                next_year += 1
                next_month = 1

    def __day_iterator(
        self, start_year: int, start_month: int, start_day: int
    ) -> typing.Generator[int, None, None]:
        """ Internal generator that iterates over days
        """

        def weekday(d: int) -> int:
            return calendar.weekday(start_year, start_month, d) + 1  # weekday returns values between 0 and 6

        def switch_day(d: int, max_days: int, dow: typing.Optional[int]) -> typing.Optional[int]:
            if dow is None:
                if d < max_days:
                    return d + 1
                return None

            result = d + 7 + dow - weekday(d)
            if result <= max_days:
                return result
            return None

        days_in_month = calendar.monthrange(start_year, start_month)[1]
        iter_day_of_month = self.day_of_month()
        iter_day_of_week = self.day_of_week()

        if iter_day_of_month is not None:
            if start_day <= iter_day_of_month <= days_in_month:
                if iter_day_of_week is None or weekday(iter_day_of_month) == iter_day_of_week:
                    yield iter_day_of_month
            return

        next_day = start_day
        if iter_day_of_week and weekday(next_day) != iter_day_of_week:
            next_day = switch_day(next_day, days_in_month, iter_day_of_week)  # type: ignore[assignment] # mypy issues

        while next_day is not None:
            yield next_day
            next_day = switch_day(next_day, days_in_month, iter_day_of_week)  # type: ignore[assignment] # mypy issues

    def __time_iterator(
        self, start_time: int, max_time: int, cron_spec: typing.Optional[int]
    ) -> typing.Generator[int, None, None]:
        """ Internal generator that iterates over time
        """
        if cron_spec:
            if start_time <= cron_spec:
                yield cron_spec
            return

        next_time = start_time
        while next_time <= max_time:
            yield next_time
            next_time += 1

    @classmethod
    def from_string(cls, schedule: str) -> 'CronSchedule':
        """ Parse a string and return a schedule
        """
        # TODO: replace with regexp
        return cls.parse_tokens(*tuple(filter(lambda x: len(x) > 0, schedule.strip().split(' '))))

    @classmethod
    def parse_tokens(cls, *str_tokens: str) -> 'CronSchedule':
        """ Parse a string tokens and return a schedule
        """
        if len(str_tokens) != 5:
            raise ValueError('Malformed cron-schedule')

        int_tokens = [int(x) if x != '*' else None for x in str_tokens]

        return cls(
            minute=int_tokens[0],
            hour=int_tokens[1],
            day_of_month=int_tokens[2],
            day_of_week=int_tokens[3],
            month=int_tokens[4]
        )


class CronRecordInitError(Exception):
    """ Raises when the :class:`.CronScheduleRecord` class has initialization issues (object is not initialized or
    initialized twice)
    """
    pass


class CronScheduleRecord:
    """ Represent a single record for a scheduler that has its cron-schedule
    """

    def __init__(self, record: ScheduleRecordProto, schedule: CronSchedule):
        """ Create a new record

        :param record: record to execute
        :param schedule: schedule at which record should be executed
        """
        self.__record = record
        self.__schedule = schedule
        self.__cron_iterator: typing.Optional[typing.Generator[datetime.datetime, None, None]] = None
        self.__next_datetime: typing.Optional[datetime.datetime] = None

    def __init_test(self, is_none: bool) -> None:
        """ Check initialization status

        :param is_none: True if this object must be initialized or False otherwise
        """
        if not is_none and self.__cron_iterator is None:
            raise CronRecordInitError('This record must be initialized before use')
        elif is_none and self.__cron_iterator is not None:
            raise CronRecordInitError('This record is initialized already')

    def init(self, start_datetime: datetime.datetime) -> None:
        """ Initialize this record

        :param start_datetime: this is a start point at which next execution time will be calculated
        """
        self.__init_test(True)
        self.__cron_iterator = self.__schedule.iterate(start_datetime)
        self.__next_datetime = next(self.__cron_iterator)

    def record(self) -> ScheduleRecordProto:
        """ Return a record for execution
        """
        return self.__record

    def next(self) -> datetime.datetime:
        """ Return next execution datetime. May be called several times
        """
        self.__init_test(False)
        return self.__next_datetime  # type: ignore[return-value]  # mypy issue, we have checked this type already

    def commit(self) -> datetime.datetime:
        """ Switch next execution datetime. After this method call the :meth:`.CronScheduleRecord.next` method
        will change value
        """
        self.__init_test(False)
        self.__next_datetime = next(self.__cron_iterator)  # type: ignore[arg-type]  # mypy issue
        return self.__next_datetime

    def schedule(self, start_datetime: datetime.datetime) -> typing.Generator[datetime.datetime, None, None]:
        """ Return a new generator of an internal schedule
        """
        return self.__schedule.iterate(start_datetime)

    def __lt__(self, other: 'CronScheduleRecord') -> bool:
        """ Compare two :class:`.CronScheduleRecord` objects. Is used for ordering objects
        """
        return self.next() < other.next()


class CronTaskSource(ScheduleSourceProto):
    """ The :class:`.ScheduleSourceProto` implementation that holds and triggers cron-a-like records

    :note: This class is NOT thread safe!
    """

    polling_update = Signal(int)  # this signal is related to the :meth:`.CronTaskSource.poll` method, it will be
    # emitted when a previously returned value is not valid anymore. It may happen when a new record appear,
    # or an upcoming record is removed

    def __init__(self) -> None:
        """ Create a new task source
        """
        ScheduleSourceProto.__init__(self)

        self.__records: typing.List[CronScheduleRecord] = []
        heapq.heapify(self.__records)

    def __now(self) -> datetime.datetime:
        """ Return datetime object that will be treated as "now" (as it is in UTC timezone)
        """
        return datetime.datetime.now(datetime.timezone.utc)

    def submit_record(self, record: CronScheduleRecord) -> None:
        """ Append a record to this source
        """

        # if new record updates last poll timeout a signal polling_update will be sent
        now = self.__now()
        record.init(now)

        current_record_dt = record.next()
        previous_record_dt = self.__records[0].next() if self.__records else None

        heapq.heappush(self.__records, record)

        if previous_record_dt is None or previous_record_dt > current_record_dt:
            delta = current_record_dt - now
            self.emit(self.polling_update, delta.seconds)

    def __emit_records(self) -> None:
        """ Check whether there are records that are ready to be executed (their time has come)
        """
        records_expired = True
        now = self.__now()
        records_to_emit = []

        while records_expired and self.__records:
            cron_record = self.__records[0]
            if cron_record.next() <= now:
                records_to_emit.append(heapq.heappop(self.__records))
            else:
                records_expired = False

        for cron_record in records_to_emit:
            cron_record.commit()
            self.emit(self.task_scheduled, cron_record.record())
            heapq.heappush(self.__records, cron_record)

    def poll(self) -> typing.Optional[int]:
        """ Trigger emitting records which time has come. And return number of seconds to wait for next records

        :return: number of seconds to wait if there is at least one record to wait, and return None otherwise
        """
        " ScheduleSourceProto.task_scheduled will be emitted if require "

        if not self.__records:
            return None

        self.__emit_records()
        cron_record = self.__records[0]
        delta = self.__now() - cron_record.next()
        return delta.seconds

    def records(self) -> typing.Generator[CronScheduleRecord, None, None]:
        """ Return generator that yields record this source has
        """
        for i in self.__records.copy():
            yield i

    def discard_record(self, record: CronScheduleRecord) -> None:
        """ Remove a record from this source

        :param record: a record to remove from this source
        """
        for i in range(len(self.__records)):
            if self.__records[i] == record:
                self.__records.pop(i)
                if self.__records:
                    delta = self.__now() - self.__records[0].next()
                    self.emit(self.polling_update, delta.seconds)
                return
        raise ValueError('Unable to find a record')
