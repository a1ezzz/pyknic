# -*- coding: utf-8 -*-
# pyknic/lib/tasks/proto.py
#
# Copyright (C) 2016-2024 the pyknic authors and contributors
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

# TODO: document the code
# TODO: write tests for the code

import typing

from abc import abstractmethod
from dataclasses import dataclass

from pyknic.lib.x_mansion import CapabilitiesAndSignals
from pyknic.lib.signals.proto import Signal
from pyknic.lib.capability import capability


class RequirementsLoopError(Exception):
    """ This exception is raised when there is an attempt to start/stop tasks with mutual dependencies
    """
    pass


class TaskStartError(Exception):
    """ This exception is raised when there is an error in starting a task
    """
    pass


class TaskStopError(Exception):
    """ This exception is raised when there is an error in stopping a task
    """
    pass


class NoSuchTaskError(Exception):
    """ This exception is raised when there is no requested task (it may be a request to start unknown task or
    request to stop already stopped task)
    """
    pass


@dataclass
class TaskResult:
    """ This class is used along with a completion signal defining a result of a completed task. In order to check
    whether a task was completed successfully the 'exception' property should be checked

    :note: the 'result' property may be not the same as the result from the original :meth:`TaskProto.start`
    method call
    """
    result: typing.Any = None                         # a result of completed record (if any)
    exception: typing.Optional[BaseException] = None  # an exception raised within a task (if any)


class TaskProto(CapabilitiesAndSignals):
    """ Basic task prototype. Derived classes must implement the only thing - :meth:`WTaskProto.start`
    """

    task_started = Signal()              # a task started
    task_completed = Signal(TaskResult)  # a task completed
    task_stopped = Signal()              # a task stopped
    task_terminated = Signal()           # a task terminated

    @abstractmethod
    def start(self) -> None:
        """ Start a task
        """
        raise NotImplementedError('This method is abstract')

    @capability
    def stop(self) -> None:
        """ Try to stop this task gracefully.

        :raise NotImplementedError: if this task can not be stopped
        """
        raise NotImplementedError('The "stop" method is not supported')

    @capability
    def terminate(self) -> None:
        """ Try to stop this task at all costs

        :raise NotImplementedError: if this task can not be terminated
        """
        raise NotImplementedError('The "terminate" method is not supported')
