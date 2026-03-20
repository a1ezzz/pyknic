# -*- coding: utf-8 -*-
# pyknic/lib/bellboy/models.py
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
import typing

import pydantic


@enum.unique
class SecretBackendType(enum.Enum):
    keyring = "keyring"
    shm = "shm"


@enum.unique
class FormattingMode(enum.Enum):
    json = "json"
    rich = "rich"


class CommonBellBoyCommandModel(pydantic.BaseModel):
    formatting: typing.Optional[FormattingMode] = pydantic.Field(
        validation_alias=pydantic.AliasChoices('f', 'formatting'),
        default=None,
        description='the way result will be displayed in console'
    )
    config: typing.Optional[str] = pydantic.Field(
        validation_alias=pydantic.AliasChoices('c', 'config'),
        default=None,
        description='configuration file for this utility'
    )

    model_config = pydantic.ConfigDict(validate_by_alias=True, validate_by_name=True)


class LobbyUrlBellBoyCommandModel(pydantic.BaseModel):

    lobby_url: str = pydantic.Field(
        validation_alias=pydantic.AliasChoices('l', 'lobby-url'),
        description='pyknic server url'
    )

    model_config = pydantic.ConfigDict(validate_by_alias=True, validate_by_name=True)


class SecretBackendBellBoyCommandModel(pydantic.BaseModel):

    secret_backend: SecretBackendType = pydantic.Field(
        validation_alias=pydantic.AliasChoices('s', 'secret-backend'),
        description='defines how temporary session key will be stored '
        '(interaction with the storage is not concurrently safe!)'
    )

    model_config = pydantic.ConfigDict(validate_by_alias=True, validate_by_name=True)


class GeneralBellBoyCommandModel(LobbyUrlBellBoyCommandModel, SecretBackendBellBoyCommandModel):
    model_config = pydantic.ConfigDict(validate_by_alias=True, validate_by_name=True)


class OptionalBellBoyCommandModel(pydantic.BaseModel):
    server: typing.Optional[GeneralBellBoyCommandModel] = None
