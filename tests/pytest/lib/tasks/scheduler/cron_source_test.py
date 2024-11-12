# -*- coding: utf-8 -*-

import pytest
import typing

from datetime import datetime, timezone

if typing.TYPE_CHECKING:
    # noinspection PyUnresolvedReferences
    from conftest import SignalsRegistry

from pyknic.lib.tasks.plain_task import PlainTask
from pyknic.lib.tasks.scheduler.record import ScheduleRecord
from pyknic.lib.tasks.scheduler.cron_source import CronSchedule, CronRecordInitError, CronScheduleRecord, CronTaskSource


def test_exceptions() -> None:
    assert(issubclass(CronRecordInitError, Exception) is True)


class TestCronSchedule:

    iter_init_date = datetime(year=2016, month=10, day=27, hour=22, minute=59, second=10, tzinfo=timezone.utc)

    @pytest.mark.parametrize(
        "cron_schedule, results", [
            (
                "20 20 10 * 10",
                (
                    datetime(year=2017, month=10, day=10, hour=20, minute=20, second=0, tzinfo=timezone.utc),
                    datetime(year=2018, month=10, day=10, hour=20, minute=20, second=0, tzinfo=timezone.utc),
                    datetime(year=2019, month=10, day=10, hour=20, minute=20, second=0, tzinfo=timezone.utc),
                )
            ),

            (
                "* * * * *",
                (
                    datetime(year=2016, month=10, day=27, hour=22, minute=59, second=0, tzinfo=timezone.utc),
                    datetime(year=2016, month=10, day=27, hour=23, minute=0, second=0, tzinfo=timezone.utc),
                    datetime(year=2016, month=10, day=27, hour=23, minute=1, second=0, tzinfo=timezone.utc),
                )
            ),

            (
                "10 * * * *",
                (
                    datetime(year=2016, month=10, day=27, hour=23, minute=10, second=0, tzinfo=timezone.utc),
                    datetime(year=2016, month=10, day=28, hour=0, minute=10, second=0, tzinfo=timezone.utc),
                    datetime(year=2016, month=10, day=28, hour=1, minute=10, second=0, tzinfo=timezone.utc),
                )
            ),

            (
                "* 10 * * *",
                (
                    datetime(year=2016, month=10, day=28, hour=10, minute=0, second=0, tzinfo=timezone.utc),
                    datetime(year=2016, month=10, day=28, hour=10, minute=1, second=0, tzinfo=timezone.utc),
                    datetime(year=2016, month=10, day=28, hour=10, minute=2, second=0, tzinfo=timezone.utc),
                )
            ),

            (
                "* * 10 * *",
                (
                    datetime(year=2016, month=11, day=10, hour=0, minute=0, second=0, tzinfo=timezone.utc),
                    datetime(year=2016, month=11, day=10, hour=0, minute=1, second=0, tzinfo=timezone.utc),
                    datetime(year=2016, month=11, day=10, hour=0, minute=2, second=0, tzinfo=timezone.utc),
                )
            ),

            (
                "* * * 2 *",
                (
                    datetime(year=2016, month=11, day=1, hour=0, minute=0, second=0, tzinfo=timezone.utc),
                    datetime(year=2016, month=11, day=1, hour=0, minute=1, second=0, tzinfo=timezone.utc),
                    datetime(year=2016, month=11, day=1, hour=0, minute=2, second=0, tzinfo=timezone.utc),
                )
            ),

            (
                "* * * * 6",
                (
                    datetime(year=2017, month=6, day=1, hour=0, minute=0, second=0, tzinfo=timezone.utc),
                    datetime(year=2017, month=6, day=1, hour=0, minute=1, second=0, tzinfo=timezone.utc),
                    datetime(year=2017, month=6, day=1, hour=0, minute=2, second=0, tzinfo=timezone.utc),
                )
            ),

            (
                "15 13 11 * *",
                (
                    datetime(year=2016, month=11, day=11, hour=13, minute=15, second=0, tzinfo=timezone.utc),
                    datetime(year=2016, month=12, day=11, hour=13, minute=15, second=0, tzinfo=timezone.utc),
                    datetime(year=2017, month=1, day=11, hour=13, minute=15, second=0, tzinfo=timezone.utc),
                )
            ),

            (
                "15 13 * 2 *",
                (
                    datetime(year=2016, month=11, day=1, hour=13, minute=15, second=0, tzinfo=timezone.utc),
                    datetime(year=2016, month=11, day=8, hour=13, minute=15, second=0, tzinfo=timezone.utc),
                    datetime(year=2016, month=11, day=15, hour=13, minute=15, second=0, tzinfo=timezone.utc),
                )
            ),

            (
                "7 7 * * *",
                (
                    datetime(year=2016, month=10, day=28, hour=7, minute=7, second=0, tzinfo=timezone.utc),
                    datetime(year=2016, month=10, day=29, hour=7, minute=7, second=0, tzinfo=timezone.utc),
                    datetime(year=2016, month=10, day=30, hour=7, minute=7, second=0, tzinfo=timezone.utc),
                    datetime(year=2016, month=10, day=31, hour=7, minute=7, second=0, tzinfo=timezone.utc),
                    datetime(year=2016, month=11, day=1, hour=7, minute=7, second=0, tzinfo=timezone.utc),
                    datetime(year=2016, month=11, day=2, hour=7, minute=7, second=0, tzinfo=timezone.utc),
                )
            ),

            (
                "7 7 7 7 7",
                (
                    datetime(year=2019, month=7, day=7, hour=7, minute=7, second=0, tzinfo=timezone.utc),
                    datetime(year=2024, month=7, day=7, hour=7, minute=7, second=0, tzinfo=timezone.utc),
                    datetime(year=2030, month=7, day=7, hour=7, minute=7, second=0, tzinfo=timezone.utc),
                    datetime(year=2041, month=7, day=7, hour=7, minute=7, second=0, tzinfo=timezone.utc),
                )
            ),

        ]
    )
    def test(self, cron_schedule: str, results: typing.Tuple[datetime]) -> None:
        schedule = CronSchedule.from_string(cron_schedule)
        cron_iterator = schedule.iterate(TestCronSchedule.iter_init_date)
        for r in results:
            assert(next(cron_iterator) == r)

    def test_exception(self) -> None:
        schedule = CronSchedule.from_string("* * * * *")

        with pytest.raises(ValueError):
            schedule.iterate(datetime.now())  # doesn't have tzinfo -- exception is raised

        with pytest.raises(ValueError):
            CronSchedule.from_string("* * 31 * 2")  # there is no 31th of Februrary

        with pytest.raises(ValueError):
            CronSchedule.from_string("* *")  # tokens are not enough

        with pytest.raises(ValueError):
            CronSchedule.from_string("* * * * * *")  # too many tokens


class TestCronScheduleRecord:

    def test_plain(self) -> None:
        record = ScheduleRecord(PlainTask(lambda: None))
        schedule = CronSchedule.from_string("* * * * *")
        cron_record = CronScheduleRecord(record, schedule)

        assert(cron_record.record() is record)

    @pytest.mark.parametrize(
        "method_name", [
            "next",
            "commit"
        ]
    )
    def test_uninitialized_record(self, method_name: str) -> None:
        record = ScheduleRecord(PlainTask(lambda: None))
        schedule = CronSchedule.from_string("* * * * *")
        cron_record = CronScheduleRecord(record, schedule)

        with pytest.raises(CronRecordInitError):
            getattr(cron_record, method_name)()

    def test_double_init(self) -> None:
        record = ScheduleRecord(PlainTask(lambda: None))
        schedule = CronSchedule.from_string("* * * * *")
        cron_record = CronScheduleRecord(record, schedule)

        cron_record.init(datetime.now(timezone.utc))
        with pytest.raises(CronRecordInitError):
            cron_record.init(datetime.now(timezone.utc))

    def test_next(self) -> None:
        record = ScheduleRecord(PlainTask(lambda: None))
        schedule = CronSchedule.from_string("* * * * *")
        cron_record = CronScheduleRecord(record, schedule)
        start_datetime = datetime(year=2001, month=1, day=1, hour=1, minute=1, second=0, tzinfo=timezone.utc)

        cron_record.init(start_datetime)
        next_datetime = cron_record.next()
        assert(next_datetime == datetime(year=2001, month=1, day=1, hour=1, minute=1, second=0, tzinfo=timezone.utc))

        next_datetime = cron_record.next()
        assert(next_datetime == datetime(year=2001, month=1, day=1, hour=1, minute=1, second=0, tzinfo=timezone.utc))

        cron_record.commit()
        next_datetime = cron_record.next()
        assert(next_datetime == datetime(year=2001, month=1, day=1, hour=1, minute=2, second=0, tzinfo=timezone.utc))

        next_datetime = cron_record.next()
        assert(next_datetime == datetime(year=2001, month=1, day=1, hour=1, minute=2, second=0, tzinfo=timezone.utc))

        cron_record.commit()
        next_datetime = cron_record.next()
        assert(next_datetime == datetime(year=2001, month=1, day=1, hour=1, minute=3, second=0, tzinfo=timezone.utc))

        next_datetime = cron_record.next()
        assert(next_datetime == datetime(year=2001, month=1, day=1, hour=1, minute=3, second=0, tzinfo=timezone.utc))

    def test_schedule(self) -> None:
        record = ScheduleRecord(PlainTask(lambda: None))
        schedule = CronSchedule.from_string("* * * * *")
        cron_record = CronScheduleRecord(record, schedule)
        start_datetime = datetime(year=2001, month=1, day=1, hour=1, minute=1, second=0, tzinfo=timezone.utc)

        schedule_obj = cron_record.schedule(start_datetime)

        assert(
            next(schedule_obj) == datetime(year=2001, month=1, day=1, hour=1, minute=1, second=0, tzinfo=timezone.utc)
        )
        assert(
            next(schedule_obj) == datetime(year=2001, month=1, day=1, hour=1, minute=2, second=0, tzinfo=timezone.utc)
        )
        assert(
            next(schedule_obj) == datetime(year=2001, month=1, day=1, hour=1, minute=3, second=0, tzinfo=timezone.utc)
        )
        assert(
            next(schedule_obj) == datetime(year=2001, month=1, day=1, hour=1, minute=4, second=0, tzinfo=timezone.utc)
        )


class TestCronTaskSource:

    def test(self) -> None:
        source = CronTaskSource()
        assert(source.poll() is None)
        assert(list(source.records()) == [])

    def test_polling(self, signals_registry: 'SignalsRegistry') -> None:
        source = CronTaskSource()
        record = ScheduleRecord(PlainTask(lambda: None))
        cron_schedule = CronScheduleRecord(record, CronSchedule.from_string("* * * * *"))

        source.callback(CronTaskSource.task_scheduled, signals_registry)
        source.submit_record(cron_schedule)
        source.poll()

        assert(signals_registry.dump(True) == [
            (source, CronTaskSource.task_scheduled, record),
        ])

        source.poll()
        assert(signals_registry.dump(True) == [])

    def test_records(self, signals_registry: 'SignalsRegistry') -> None:
        record = ScheduleRecord(PlainTask(lambda: None))
        now = datetime.now(timezone.utc)

        cron_schedule1 = CronScheduleRecord(record, CronSchedule.from_string(f"* {(now.hour + 4) % 24} * * *"))
        cron_schedule2 = CronScheduleRecord(record, CronSchedule.from_string(f"* {(now.hour + 3) % 24} * * *"))
        cron_schedule3 = CronScheduleRecord(record, CronSchedule.from_string(f"* {(now.hour + 5) % 24} * * *"))

        source = CronTaskSource()
        source.callback(CronTaskSource.polling_update, signals_registry)

        source.submit_record(cron_schedule1)
        signals = signals_registry.dump(True)
        ttl1 = signals[0][2]
        assert(len(signals) == 1)
        assert(signals[0][1] == CronTaskSource.polling_update)
        assert(ttl1 > 0)  # type: ignore[operator]  # it's a test

        source.submit_record(cron_schedule2)
        signals = signals_registry.dump(True)
        ttl2 = signals[0][2]
        assert(len(signals) == 1)
        assert(signals[0][1] == CronTaskSource.polling_update)
        assert(ttl2 > 0)  # type: ignore[operator]  # it's a test
        assert(ttl2 < ttl1)  # type: ignore[operator]  # it's a test

        source.submit_record(cron_schedule3)
        assert(signals_registry.dump(True) == [])  # no polling update is required

        assert(list(source.records()) == [cron_schedule2, cron_schedule1, cron_schedule3])

    def test_discard(self, signals_registry: 'SignalsRegistry') -> None:
        record = ScheduleRecord(PlainTask(lambda: None))
        now = datetime.now(timezone.utc)

        cron_schedule1 = CronScheduleRecord(record, CronSchedule.from_string(f"* {(now.hour + 4) % 24} * * *"))
        cron_schedule2 = CronScheduleRecord(record, CronSchedule.from_string(f"* {(now.hour + 3) % 24} * * *"))
        cron_schedule3 = CronScheduleRecord(record, CronSchedule.from_string(f"* {(now.hour + 5) % 24} * * *"))

        source = CronTaskSource()
        source.submit_record(cron_schedule1)
        source.submit_record(cron_schedule2)
        source.submit_record(cron_schedule3)

        source.callback(CronTaskSource.polling_update, signals_registry)

        source.discard_record(cron_schedule2)
        signals = signals_registry.dump(True)
        ttl1 = signals[0][2]
        assert(len(signals) == 1)
        assert(signals[0][1] == CronTaskSource.polling_update)
        assert(ttl1 > 0)  # type: ignore[operator]  # it's a test

        source.discard_record(cron_schedule1)
        signals = signals_registry.dump(True)
        ttl2 = signals[0][2]
        assert(len(signals) == 1)
        assert(signals[0][1] == CronTaskSource.polling_update)
        assert(ttl2 > 0)  # type: ignore[operator]  # it's a test
        assert(ttl2 < ttl1)  # type: ignore[operator]  # it's a test

        assert(list(source.records()) == [cron_schedule3])

        with pytest.raises(ValueError):
            source.discard_record(cron_schedule1)

        source.discard_record(cron_schedule3)  # no mo records left
        assert(signals_registry.dump(True) == [])
