# -*- coding: utf-8 -*-
import logging

import pytest
import typing
import uuid

from pyknic.tasks.log import LogTask
from pyknic.lib.datalog.proto import DatalogProto
from pyknic.lib.log import Logger


@pytest.fixture
def reset_logger() -> typing.Generator[None, None, None]:
    yield None
    current_handlers = Logger.handlers.copy()
    Logger.setLevel(logging.NOTSET)
    for h in current_handlers:
        Logger.removeHandler(h)


class TestLogTask:

    def test(self, monkeypatch: pytest.MonkeyPatch, empty_datalog: DatalogProto, reset_logger: None) -> None:
        assert(LogTask.dependencies() is None)
        task = LogTask.create(empty_datalog, 'sample-api-id', uuid.uuid4())
        assert(task.task_name() is not None)

        with pytest.raises(ValueError):
            task.start()

        monkeypatch.setenv(LogTask.__env_var_name__, "FOO")

        with pytest.raises(ValueError):
            task.start()

        monkeypatch.setenv(LogTask.__env_var_name__, "DEBUG")
        task.start()
