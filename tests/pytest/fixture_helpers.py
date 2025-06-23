# -*- coding: utf-8 -*-
# tests/pytest/fixture_helpers.py
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

import typing


class BaseFixture:

    @classmethod
    def start(cls) -> typing.Any:
        pass

    @classmethod
    def finalize(cls, start_result: typing.Any):
        pass


def pyknic_fixture(fixture_cls):
    result = fixture_cls.start()
    yield result
    fixture_cls.finalize(result)
