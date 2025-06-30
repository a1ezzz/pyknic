# -*- coding: utf-8 -*-
# pyknic/lib/fastapi/models/lobby.py
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

# TODO: document the code
# TODO: write tests for the code

import typing

import pydantic


class LobbyKeyWordArgs(pydantic.BaseModel):
    pass


class LobbyContextArg(pydantic.BaseModel):
    pass


class LobbyCommand(pydantic.BaseModel):
    name: str = pydantic.Field(min_length=1)
    args: typing.Tuple[()] | None = None
    kwargs: LobbyKeyWordArgs | None = None
    cargs: LobbyContextArg | None = None


class LobbyCommandResult(pydantic.BaseModel):
    # TODO: there may be predefined properties as the "status" (0 -- command scheduled,
    #  1 -- command completed successfully, 2 -- command completed with error)
    pass
