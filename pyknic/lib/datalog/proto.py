# -*- coding: utf-8 -*-
# pyknic/lib/datalog/proto.py
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

from abc import abstractmethod

from pyknic.lib.signals.proto import Signal
from pyknic.lib.signals.source import SignalSource


class DatalogProto(SignalSource):
    """ This class represent sequence of data, where new data may be updated to the tail only
    """

    new_entry = Signal(object)

    @abstractmethod
    def append(self, record: typing.Any) -> None:
        """ Append new data to the end of sequence

        :param record: data to update
        """
        raise NotImplementedError('This method is abstract')

    @abstractmethod
    def iterate(self, reverse: bool = False) -> typing.Generator[typing.Any, None, None]:
        """ Return iterator that yields over saved data from the oldest one to a newer one

        :param reverse: whether to return from the newer record to the oldest one (in case of True) and
        return in default order otherwise
        """
        raise NotImplementedError('This method is abstract')

    @abstractmethod
    def truncate(self, min_length: int) -> None:
        """ Remove old records and keep at least N records

        :param min_length: number of records in sequence to keep. Not less than this number of records will be kept
        """
        raise NotImplementedError('This method is abstract')

    def find(
        self, filter_fn: typing.Callable[[typing.Any], bool], reverse: bool = False
    ) -> typing.Optional[typing.Any]:
        """ Try to find the closest entry that is suitable to the filter function

        :param filter_fn: a function that returns True for suitable log entry
        :param reverse: if False return the oldest record and return the newest record otherwise
        """
        raise NotImplementedError('This method is abstract')
