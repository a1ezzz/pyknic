# -*- coding: utf-8 -*-
# pyknic/lib/io/stats.py
#
# Copyright (C) 2025 the pyknic authors and contributors
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


import time
import typing

from pyknic.lib.io import IOGenerator, IOProducer


class GeneratorStats:
    """This IOProcessor is used for some statistics calculation.
    """

    def __init__(self) -> None:
        """Create and initialize statistics
        """
        self.__start_time: typing.Optional[float] = None
        self.__finish_time: typing.Optional[float] = None
        self.__bytes = 0

    def rate(self) -> float:
        """Return number of processed bytes from an original source per second. This method is available only after
        the generator has been finished.
        """
        if self.__finish_time is None:
            raise RuntimeError('The generator has not been finished')

        elapsed = self.__finish_time - self.__start_time  # type: ignore[operator]
        return float(self.__bytes) / elapsed

    def bytes(self) -> int:
        """Return number of processed bytes from an original source. This method is available only after the generator
        has been finished.
        """
        if self.__finish_time is None:
            raise RuntimeError('The generator has not been finished')
        return self.__bytes

    def process(self, source: IOProducer) -> IOGenerator:
        """Process a source and calculate statistics.

        :param source: source which statistics should be calculated
        """
        if self.__start_time is None:
            self.__start_time = time.monotonic()

        for i in source:
            self.__bytes += len(i)
            yield i

        self.__finish_time = time.monotonic()
