# -*- coding: utf-8 -*-
# pyknic/lib/i12n.py
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

# TODO: document the code; i12n -- implementation
# TODO: write tests for the code

import typing

from pyknic.lib.registry import APIRegistryProto, register_api


def register_implementation(
    registry: APIRegistryProto, api_id: type
) -> typing.Callable[..., typing.Callable[..., type]]:

    def decorator_fn(decorated_obj: type) -> typing.Callable[..., type]:
        if not issubclass(decorated_obj, api_id):
            raise NotImplementedError(
                f'The "{decorated_obj.__name__}" class must derived from the "{api_id.__name__}" base class'
            )
        return register_api(registry, api_id)(decorated_obj)

    return decorator_fn
