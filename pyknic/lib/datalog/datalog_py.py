# -*- coding: utf-8 -*-
# pyknic/lib/datalog/datalog_py.py
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

from pyknic.lib.verify import verify_value

from pyknic.lib.datalog.proto import DatalogProto
from pyknic.lib.thread import CriticalResource


class DatalogPy(DatalogProto, CriticalResource):
    """ The :class:`.DatalogProto` implementation in Python with locks
    """

    def __init__(self, cr_timeout: typing.Union[int, float, None] = None):
        """ Create a new log

        :param cr_timeout: timeout for a lock acquiring
        """
        DatalogProto.__init__(self)
        CriticalResource.__init__(self, cr_timeout)
        self.__log: typing.List[typing.Any] = list()

    @CriticalResource.critical_section
    def append(self, record: typing.Any) -> None:
        """ The :meth:`.DatalogPy.append` method implementation
        """
        self.__log.append(record)

    def iterate(self) -> typing.Generator[typing.Any, None, None]:
        """ The :meth:`.DatalogPy.iterate` method implementation
        """

        with self.critical_context():
            log_copy = self.__log.copy()

        for i in log_copy:
            yield i

    @verify_value(min_length=lambda x: x >= 0)
    @CriticalResource.critical_section
    def truncate(self, min_length: int) -> None:
        """ The :meth:`.DatalogPy.truncate` method implementation
        """

        if min_length == 0:
            self.__log.clear()
        else:
            self.__log = self.__log[-min_length:]
