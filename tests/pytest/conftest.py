# -*- coding: utf-8 -*-

from fixtures.callbacks_n_signals import callbacks_registry, signals_registry, signal_watcher
from fixtures.callbacks_n_signals import CallbackRegistry, SignalsRegistry, SignalWatcher
from fixtures.tasks import sample_tasks, empty_datalog, SampleTasks
from fixtures.fastapi import fastapi_fixture, fastapi_class_fixture, fastapi_module_fixture, fastapi_package_fixture
from fixtures.fastapi import fastapi_session_fixture, AsyncFastAPIFixture
from fixtures.config import config_file
from fixtures.gettext import gettext
from fixtures.event_loop import event_loop, class_event_loop, module_event_loop, package_event_loop, session_event_loop

__all__ = [
    "callbacks_registry",
    "config_file",
    "empty_datalog",

    "event_loop",
    "class_event_loop",
    "module_event_loop",
    "package_event_loop",
    "session_event_loop",

    "fastapi_fixture",
    "fastapi_class_fixture",
    "fastapi_module_fixture",
    "fastapi_package_fixture",
    "fastapi_session_fixture",

    "gettext",

    "sample_tasks",
    "signals_registry",
    "signal_watcher",

    "AsyncFastAPIFixture",
    "CallbackRegistry",
    "SampleTasks",
    "SignalsRegistry",
    "SignalWatcher"
]
