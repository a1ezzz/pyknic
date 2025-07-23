# -*- coding: utf-8 -*-
# pyknic/lib/tasks/thread_executor.py
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
import types
import typing

from pyknic.lib.signals.extra import SignalResender
from pyknic.lib.signals.proto import Signal
from pyknic.lib.signals.source import SignalSource
from pyknic.lib.thread import CriticalResource
from pyknic.lib.verify import verify_value

from pyknic.lib.tasks.proto import TaskExecutorProto, TaskProto, NoSuchTaskError, TaskStartError
from pyknic.lib.tasks.threaded_task import ThreadedTask


class NoFreeSlotError(Exception):
    """ This exception is raised when there is no free slots available
    """
    pass


class ThreadExecutor(TaskExecutorProto, CriticalResource, SignalSource):
    """ The :class:`.TaskExecutorProto` class implementation, that executes tasks in dedicated threads
    """
    # TODO: do not start thread every time but reuse them

    task_completed = Signal(TaskProto)  # this signal is emitted when a task is about to complete

    class Context:
        """ A context that is allocated with a free slot in a pool
        """

        def __init__(
            self,
            executor: 'ThreadExecutor',
            submit_fn: typing.Callable[[TaskProto, bool], ThreadedTask],
            release_fn: typing.Callable[[], None]
        ):
            """ Prepare a context

            :param executor: executor that creates this context
            :param submit_fn: a function that submits a task
            :param release_fn: a function that release a slot if a task wasn't started
            """
            self.__executor = executor
            self.__submit_fn = submit_fn
            self.__release_fn = release_fn
            self.__task_submitted = False

        def __enter__(self) -> 'ThreadExecutor.Context':
            """ Enter a context
            """
            return self

        def __exit__(
            self,
            exc_type: typing.Optional[typing.Type[BaseException]],
            exc_val: typing.Optional[BaseException],
            exc_tb: typing.Optional[types.TracebackType]
        ) -> None:
            """ Exit this context and free slot if a task wasn't started
            """
            if not self.__task_submitted:
                self.__release_fn()

        def submit_task(self, task: TaskProto, start_task: bool = True) -> ThreadedTask:
            """ Try to submit a task

            :param task: a task to start
            :param start_task: whether to start a task immediately
            """
            if self.__task_submitted:
                raise TaskStartError('This context is used already')

            result = self.__submit_fn(task, start_task)
            self.__task_submitted = True
            return result

    @verify_value(threads_number=lambda x: x is None or x > 0)
    def __init__(
        self,
        threads_number: typing.Optional[int] = None,
        executor_cr_timeout: typing.Union[int, float, None] = None,
        thread_cr_timeout: typing.Union[int, float, None] = None
    ):
        """ Create a new executor

        :param threads_number: if defined then this is a maximum number of concurrent running tasks
        :param executor_cr_timeout: this timeout for accessing internal critical resources
        :param thread_cr_timeout: a timeout with which an :class:`.ThreadedTask` object will be created (the same
        as the cr_timeout in the ::meth:`.ThreadedTask.__init__` method)
        """
        TaskExecutorProto.__init__(self)
        CriticalResource.__init__(self, executor_cr_timeout)
        SignalSource.__init__(self)

        self.__threads_semaphore = threading.Semaphore(threads_number) if threads_number else None
        self.__thread_cr_timeout = thread_cr_timeout

        self.__running_threads: typing.Dict[TaskProto, ThreadedTask] = dict()

        self.__signal_resender = SignalResender(self, target_signal=ThreadExecutor.task_completed)

    def __submit_task(self, task: TaskProto, start_task: bool = True) -> ThreadedTask:
        """ Try to start a task

        :param task: a task to start
        """
        task_id = task.task_name() if task.task_name() else str(task)
        result = ThreadedTask(task, self.__thread_cr_timeout, thread_name=f'pyknic:thexec:{task_id}')  # noqa: E231

        with self.critical_context():
            if task in self.__running_threads:
                raise TaskStartError('A task has been submitted already')
            self.__running_threads[task] = result

        result.callback(ThreadedTask.thread_ready, self.__signal_resender)
        if start_task:
            result.start()
        return result

    def __release_slot(self) -> None:
        """ Release a slot (if they are limited)
        """
        if self.__threads_semaphore:
            self.__threads_semaphore.release()

    def submit_task(self, task: TaskProto) -> bool:
        """ The :meth:`.TaskExecutorProto.submit_task` implementation
        """

        try:
            with self.executor_context() as c:
                c.submit_task(task)
                return True
        except (TaskStartError, NoFreeSlotError):
            return False

    def complete_task(self, task: TaskProto) -> bool:
        """ The :meth:`.TaskExecutorProto.complete_task` implementation
        """
        with self.critical_context():
            if task not in self.__running_threads:
                raise NoSuchTaskError('Unable to find a task')
            threaded_task = self.__running_threads[task]

            join_result = threaded_task.join()
            if not join_result:
                return False

            self.__running_threads.pop(task)

        self.__release_slot()
        return True

    def executor_context(self) -> 'ThreadExecutor.Context':
        """ Allocate a slot for a task and return a context
        """
        if self.__threads_semaphore and not self.__threads_semaphore.acquire(False):
            raise NoFreeSlotError("Unable to allocate a slot of the executor's pool")

        return ThreadExecutor.Context(self, self.__submit_task, self.__release_slot)

    def tasks(self) -> typing.Generator[TaskProto, None, None]:
        """ Return started tasks
        """
        with self.critical_context():
            tasks = list(self.__running_threads.keys())

        for i in tasks:
            yield i

    def wait_task(self, task: TaskProto, timeout: typing.Union[int, float, None] = None) -> bool:
        """ The :meth:`.TaskExecutorProto.wait_task` implementation
        """
        with self.critical_context():
            if task not in self.__running_threads:
                raise NoSuchTaskError('Unable to find a task')
            threaded_task = self.__running_threads[task]

        if timeout is None:
            threaded_task.wait()
            return True
        elif timeout > 0:
            threaded_task.wait(timeout=timeout)

        return threaded_task.join()  # type: ignore[no-any-return]  # mypy and decorator's issue

    async def start_async(self, task: TaskProto) -> None:
        """ The :meth:`.TaskExecutorProto.start_async` implementation
        """

        with self.executor_context() as c:
            threaded_task = c.submit_task(task, start_task=False)
            await threaded_task.start_async()
