# -*- coding: utf-8 -*-
# pyknic/environment.py
#
# Copyright (C) 2026 the pyknic authors and contributors
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

import enum
import os

import pydantic_settings


@enum.unique
class PyknicLogLevel(enum.Enum):
    ERROR = 'ERROR'
    WARNING = 'WARNING'
    INFO = 'INFO'
    DEBUG = 'DEBUG'


class PyknicEnvVars(pydantic_settings.BaseSettings):

    model_config = pydantic_settings.SettingsConfigDict(env_prefix='PYKNIC_', )

    app_name: str = 'pyknic'
    log_level: PyknicLogLevel = PyknicLogLevel.INFO
    plugins: str = ''

    dir_config: str = ''
    file_config: str = ''

    @staticmethod
    def export_settings(**kwargs: str) -> None:
        for key, value in kwargs.items():
            os.environ['PYKNIC_' + key.upper()] = value

        _ = PyknicEnvVars()  # just to check that vars are possible to parse
