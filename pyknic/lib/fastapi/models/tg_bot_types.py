# -*- coding: utf-8 -*-
# pyknic/lib/fastapi/models/tg_bot_types.py
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

# TODO: autogenerate like this "https://github.com/AntonOvsyannikov/pure-teleapi/blob/main/apigen/__main__.py"

import pydantic
import typing


# These models are based on https://core.telegram.org/bots/api#available-types


class CallbackQuery(pydantic.BaseModel):
    # origin: https://core.telegram.org/bots/api#callbackquery
    id_: str = pydantic.Field(alias='id')
    from_: 'User' = pydantic.Field(alias='from')
    data: str | None = None

    model_config = pydantic.ConfigDict(
        populate_by_name=True,
    )


class Chat(pydantic.BaseModel):
    # origin: https://core.telegram.org/bots/api#chat
    id_: int = pydantic.Field(alias='id')
    type_: str = pydantic.Field(alias='type')  # TODO: better to do it with enum

    model_config = pydantic.ConfigDict(
        populate_by_name=True,
    )


class InlineKeyboardButton(pydantic.BaseModel):
    # origin: https://core.telegram.org/bots/api#inlinekeyboardbutton
    text: str
    callback_data: str | None = None


class InlineKeyboardMarkup(pydantic.BaseModel):
    # origin: https://core.telegram.org/bots/api#inlinekeyboardmarkup
    inline_keyboard: typing.List[typing.List[InlineKeyboardButton]]


class Message(pydantic.BaseModel):
    # origin: https://core.telegram.org/bots/api#message
    message_id: int
    from_: typing.Optional['User'] = pydantic.Field(default=None, alias='from')
    chat: Chat
    text: typing.Optional[str] = None

    model_config = pydantic.ConfigDict(
        populate_by_name=True,
    )


class ReplyParameters(pydantic.BaseModel):
    # origin: https://core.telegram.org/bots/api#replyparameters
    message_id: int


class Update(pydantic.BaseModel):
    # origin: https://core.telegram.org/bots/api#update
    update_id: int
    callback_query: CallbackQuery | None = None
    message: Message | None = None


class User(pydantic.BaseModel):
    # origin: https://core.telegram.org/bots/api#user
    id_: int = pydantic.Field(alias='id')
    language_code: str | None = None

    model_config = pydantic.ConfigDict(
        populate_by_name=True,
    )
