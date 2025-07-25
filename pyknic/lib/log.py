# -*- coding: utf-8 -*-
# pyknic/lib/log.py
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

import logging

from pyknic.lib.singleton import create_singleton


Logger: logging.Logger = create_singleton(logging.getLogger("pyknic"))  # type: ignore[assignment]  # metaclass

# TODO: check it out -- https://docs.python.org/3/library/logging.config.html
