# -*- coding: utf-8 -*-
# pyknic/lib/fastapi/apps_registry.py
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

# TODO: document the code
# TODO: write tests for the code

import fastapi

from abc import ABCMeta, abstractmethod

from pyknic.lib.registry import APIRegistry


__default_fastapi_apps_registry__ = APIRegistry()


class FastAPIAppProto(metaclass=ABCMeta):

    @classmethod
    @abstractmethod
    def create_app(cls, fastapi_app: fastapi.FastAPI) -> None:
        raise NotImplementedError('This method is abstract')
