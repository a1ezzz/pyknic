# -*- coding: utf-8 -*-

import typing

from pyknic.lib.tasks.plain_task import PlainTask
from pyknic.lib.tasks.proto import TaskProto, TaskResult

if typing.TYPE_CHECKING:
    # noinspection PyUnresolvedReferences
    from conftest import CallbackRegistry, SignalsRegistry


class TestPlainTask:

    def test(self, callbacks_registry: 'CallbackRegistry') -> None:
        plain_task = PlainTask(callbacks_registry.callback())
        assert(isinstance(plain_task, TaskProto) is True)
        plain_task.start()
        assert(callbacks_registry.total_calls() == 1)

    def test_success_result(
        self, callbacks_registry: 'CallbackRegistry',  signals_registry: 'SignalsRegistry'
    ) -> None:
        callback_result = object()
        plain_task = PlainTask(callbacks_registry.callback(callback_result=callback_result))
        plain_task.callback(plain_task.task_started, signals_registry)
        plain_task.callback(plain_task.task_completed, signals_registry)

        assert(signals_registry.dump(True) == [])
        plain_task.start()
        assert(signals_registry.dump(True) == [
            (plain_task, TaskProto.task_started, None),
            (plain_task, TaskProto.task_completed, TaskResult(callback_result)),
        ])

    def test_exception_result(
        self, callbacks_registry: 'CallbackRegistry', signals_registry: 'SignalsRegistry'
    ) -> None:
        callback_exception = ValueError('!')

        def exc() -> None:
            raise callback_exception

        plain_task = PlainTask(callbacks_registry.callback(callback_result=exc))
        plain_task.callback(plain_task.task_started, signals_registry)
        plain_task.callback(plain_task.task_completed, signals_registry)

        assert(signals_registry.dump(True) == [])
        plain_task.start()
        assert(signals_registry.dump(True) == [
            (plain_task, TaskProto.task_started, None),
            (plain_task, TaskProto.task_completed, TaskResult(exception=callback_exception)),
        ])
