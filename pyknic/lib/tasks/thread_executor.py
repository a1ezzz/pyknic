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

import typing

from dataclasses import dataclass

from pyknic.lib.verify import verify_value
from pyknic.lib.thread import CriticalResource
from pyknic.lib.signals.proto import Signal
from pyknic.lib.signals.source import SignalSource
from pyknic.lib.signals.extra import SignalResender

from pyknic.lib.tasks.proto import TaskExecutorProto, TaskProto, NoSuchTaskError, TaskResult
from pyknic.lib.tasks.threaded_task import ThreadedTask


class ThreadExecutor(TaskExecutorProto, CriticalResource, SignalSource):
    """ The :class:`.TaskExecutorProto` class implementation, that executes tasks in dedicated threads
    """

    task_completed = Signal(TaskResult)  # a result of completed task

    @dataclass
    class TaskDescriptor:
        """ This descriptor is generated for each running task (the :class:`.TaskProto` object)
        """
        threaded_task: ThreadedTask         # a started thread
        signal_resender_tc: SignalResender  # a callback object for signal resending

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

        self.__threads_number = threads_number
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
    def submit_task(self, task: TaskProto) -> bool:
        """ The :meth:`.TaskExecutorProto.submit_task` implementation
        """
        self.__join_threads()
        if self.__threads_number is not None and len(self.__running_threads) >= self.__threads_number:
            return False

        if task in self.__running_threads:
            raise ValueError('The task is already executed')

        threaded_task = ThreadedTask(task, self.__thread_cr_timeout)
        threaded_task.start()
        self.__running_threads[task] = ThreadExecutor.TaskDescriptor(
            threaded_task,
            SignalResender(
                threaded_task, self, ThreadedTask.task_completed, target_signal=ThreadExecutor.task_completed
            )
        )
        return True

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

    @CriticalResource.critical_section
    def join_task(self, task: TaskProto) -> bool:
        """ Try to "join" a task and return True if task is joined (and return False otherwise)
        """
        if task not in self.__running_threads:
            raise NoSuchTaskError(f"Unable to find a task -- {task}")

        threaded_task = self.__running_threads[task].threaded_task
        if threaded_task.join():
            self.__running_threads.pop(task)
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
