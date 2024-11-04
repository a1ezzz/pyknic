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

from dataclasses import dataclass

from pyknic.lib.verify import verify_value
from pyknic.lib.thread import CriticalResource
from pyknic.lib.signals.proto import Signal, SignalSourceProto
from pyknic.lib.signals.source import SignalSource

from pyknic.lib.tasks.proto import TaskExecutorProto, TaskProto, NoSuchTaskError, TaskResult
from pyknic.lib.tasks.threaded_task import ThreadedTask


@dataclass
class ThreadedTaskCompleted:
    """ This class represent a task completion result
    """
    task: TaskProto     # a task that has been completed
    result: TaskResult  # a result of a completed task


class ThreadExecutor(TaskExecutorProto, CriticalResource, SignalSource):
    """ The :class:`.TaskExecutorProto` class implementation, that executes tasks in dedicated threads
    """

    task_completed = Signal(ThreadedTaskCompleted)  # a result of completed task

    class TaskCompleteCallback:
        """ This callback is used for resending of completion signal
        """

        def __init__(self, executor: 'ThreadExecutor', threaded_task: ThreadedTask, task: TaskProto):
            """ Create callback

            :param executor: executor with which a task was started
            :param threaded_task: a thread of a task which signal will be caught. It is much better to use this object
            instead of TaskProto since a custom TaskProto may not implement such signal
            :param task: task which result will be emitted
            """
            self.__executor = executor
            self.__task = task

            threaded_task.callback(ThreadedTask.task_completed, self)

        def __call__(self, source: SignalSourceProto, signal: Signal, value: typing.Any) -> None:
            """ Receive completion event and resend
            """
            self.__executor.emit(ThreadExecutor.task_completed, ThreadedTaskCompleted(self.__task, value))

    @dataclass
    class TaskDescriptor:
        """ This descriptor is generated for each running task (the :class:`.TaskProto` object)
        """
        threaded_task: ThreadedTask                                 # a started thread
        task_completed_clbk: 'ThreadExecutor.TaskCompleteCallback'  # a callback object for signal resending

    class Context:
        """ A context that is allocated with a free slot in a pool
        """

        def __init__(
            self,
            executor: 'ThreadExecutor',
            submit_fn: typing.Callable[[TaskProto], None],
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
            with self.__executor.critical_context():
                if not self.__task_submitted:
                    self.__release_fn()

        def submit_task(self, task: TaskProto) -> None:
            """ Try to submit a task

            :param task: a task to start
            """
            self.__executor.join_threads()
            if self.__task_submitted:
                raise ValueError('A task has been submitted already')

            self.__submit_fn(task)
            self.__task_submitted = True

    @verify_value(threads_number=lambda x: x is None or x > 0)
    def __init__(
        self,
        threads_number: typing.Optional[int] = None,
        executor_cr_timeout: typing.Union[int, float, None] = None,
        thread_cr_timeout: typing.Union[int, float, None] = None
    ):
        """ Create a new executor

        :param threads_number: if defined then this is a maximum number of concurrent running tasks
        :param executor_cr_timeout: a timeout to gain access to this object methods
        :param thread_cr_timeout: a timeout with which an :class:`.ThreadedTask` object will be created (the same
        as the cr_timeout in the ::meth:`.ThreadedTask.__init__` method)
        """
        TaskExecutorProto.__init__(self)
        CriticalResource.__init__(self, executor_cr_timeout)
        SignalSource.__init__(self)

        self.__threads_number = threading.Semaphore(threads_number) if threads_number else None
        self.__thread_cr_timeout = thread_cr_timeout
        self.__running_threads: typing.Dict[TaskProto, ThreadExecutor.TaskDescriptor] = dict()

    @CriticalResource.critical_section
    def __len__(self) -> int:
        """ Try to "join" threads and return number of tasks that are running
        """
        self.__join_threads()
        return len(self.__running_threads)

    def __join_threads(self) -> None:
        """ Try to "join" threads that are ready and forget about them
        """
        ready_threads = set()
        for task, descriptor in self.__running_threads.items():
            if descriptor.threaded_task.join():
                ready_threads.add(task)

        for i in ready_threads:
            self.__running_threads.pop(i)

    @CriticalResource.critical_section
    def __submit_task(self, task: TaskProto) -> None:
        """ Try to start a task
        """
        if task in self.__running_threads:
            raise ValueError('The task is already executed')

        threaded_task = ThreadedTask(task, self.__thread_cr_timeout)
        callback = ThreadExecutor.TaskCompleteCallback(self, threaded_task, task)
        threaded_task.start()
        self.__running_threads[task] = ThreadExecutor.TaskDescriptor(threaded_task, callback)

    def __release_slot(self) -> None:
        """ Release a slot (if they are limited)
        """
        if self.__threads_number:
            self.__threads_number.release()

    def submit_task(self, task: TaskProto) -> bool:
        """ The :meth:`.TaskExecutorProto.submit_task` implementation
        """

        try:
            with self.executor_context() as c:
                c.submit_task(task)
                return True
        except ValueError:
            return False

    def executor_context(self) -> 'ThreadExecutor.Context':
        """ Allocate a slot for a task and return a context
        """
        if self.__threads_number and not self.__threads_number.acquire(False):
            raise ValueError("Unable to allocate a slot of the executor's pool")

        return ThreadExecutor.Context(self, self.__submit_task, self.__release_slot)

    @CriticalResource.critical_section
    def join_threads(self) -> int:
        """ Try to join threads and return True if all the threads are joined. Or return False if there is at least one
        running thread
        """
        self.__join_threads()
        return len(self.__running_threads) == 0

    def tasks(self) -> typing.Generator[TaskProto, None, None]:
        """ The :meth:`.TaskExecutorProto.tasks` implementation
        """
        with self.critical_context():
            tasks_dict = self.__running_threads.copy()

        for i in tasks_dict.keys():
            yield i

    @CriticalResource.critical_section
    def __stop_task(self, task: TaskProto, stop_method: str) -> None:
        """ Try to stop/terminate a task

        :param task: a task to stop/terminate
        :param stop_method: a name of a method to use (one of: "stop" or "terminate")
        """
        if task not in self.__running_threads:
            raise NoSuchTaskError(f"Unable to find a task -- {task}")

        threaded_task = self.__running_threads[task].threaded_task
        getattr(threaded_task, stop_method)()

    def join_task(self, task: TaskProto, await_task: bool = False) -> bool:
        """ Try to "join" a task and return True if task is joined (and return False otherwise)
        """
        with self.critical_context():
            if task not in self.__running_threads:
                raise NoSuchTaskError(f"Unable to find a task -- {task}")

            threaded_task = self.__running_threads[task].threaded_task

        if await_task:
            threaded_task.wait()

        with self.critical_context():
            if threaded_task.join():
                self.__running_threads.pop(task)
                self.__release_slot()
                return True

        return False

    def stop_task(self, task: TaskProto) -> None:
        """ The :meth:`.TaskExecutorProto.stop` implementation
        """
        self.__stop_task(task, "stop")
        self.__join_threads()

    def terminate_task(self, task: TaskProto) -> None:
        """ The :meth:`.TaskExecutorProto.terminate` implementation
        """
        self.__stop_task(task, "terminate")
        self.__join_threads()
