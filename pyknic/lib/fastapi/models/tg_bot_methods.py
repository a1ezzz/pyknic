# -*- coding: utf-8 -*-
# pyknic/lib/fastapi/models/tg_bot_methods.py
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

from pyknic.lib.fastapi.models.tg_bot_types import ReplyParameters, InlineKeyboardMarkup


# These models are based on https://core.telegram.org/bots/api#available-methods


class MethodSendMessageArgs(pydantic.BaseModel):
    # origin: https://core.telegram.org/bots/api#sendmessage
    chat_id: int | str
    text: str
    reply_parameters: ReplyParameters | None = None
    reply_markup: InlineKeyboardMarkup | None = None


class MethodSendMessage(MethodSendMessageArgs):
    # origin: https://core.telegram.org/bots/api#sendmessage
    method: typing.Literal['sendMessage'] = pydantic.Field(default='sendMessage')


class MethodAnswerCallbackQueryArgs(pydantic.BaseModel):
    # origin: https://core.telegram.org/bots/api#answercallbackquery
    callback_query_id: str
    text: str | None = None
    show_alert: bool | None = None


class MethodAnswerCallbackQuery(MethodAnswerCallbackQueryArgs):
    # origin: https://core.telegram.org/bots/api#answercallbackquery
    method: typing.Literal['answerCallbackQuery'] = pydantic.Field(default='answerCallbackQuery')
