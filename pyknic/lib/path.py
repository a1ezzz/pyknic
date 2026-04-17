# -*- coding: utf-8 -*-
# pyknic/lib/path.py
#
# Copyright (C) 2024-2026 the pyknic authors and contributors
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

import os
import pathlib
import typing

from pyknic.lib.verify import verify_value

root_path = pathlib.Path(__file__).parent.parent


@verify_value(path=lambda x: x.is_absolute())
def normalize_path(path: pathlib.PosixPath) -> pathlib.PosixPath:
    """ Normalize the given path and remove unnecessary slashes, entries and so on
    """
    # TODO: test it!
    return pathlib.PosixPath(os.path.normpath(path))


@verify_value(path=lambda x: x.is_absolute())
def split_file(path: pathlib.PosixPath) -> typing.Tuple[str, pathlib.PosixPath]:

    norm_path = normalize_path(path)

    if norm_path == norm_path.parent:
        raise ValueError(f'Path is a root path and does not have a child entry -- {norm_path}')

    return norm_path.name, norm_path.parent
