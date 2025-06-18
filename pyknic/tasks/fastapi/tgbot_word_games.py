# -*- coding: utf-8 -*-
# pyknic/tasks/fastapi/tgbot_word_games.py
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

import enum
import typing

from pyknic.lib.config import Config
from pyknic.lib.registry import register_api
from pyknic.lib.fastapi.models.tg_bot_types import InlineKeyboardMarkup, InlineKeyboardButton, Update
from pyknic.lib.fastapi.models.tg_bot_methods import MethodAnswerCallbackQuery
from pyknic.lib.fastapi.apps_registry import __default_fastapi_apps_registry__
from pyknic.tasks.fastapi.word_games.cities import TGBotCityGame
from pyknic.lib.gettext import GetTextWrapper
from pyknic.lib.fastapi.base import TgBotBaseFastAPIApp, TgBotResponseType


@register_api(__default_fastapi_apps_registry__, ":tgbot_word_games")
class TGBotWordGames(TgBotBaseFastAPIApp):

    @enum.unique
    class UserSessionMode(enum.Enum):
        null = enum.auto()
        city = enum.auto()

    def __init__(self, config: Config, translations: GetTextWrapper):
        TgBotBaseFastAPIApp.__init__(self, config, translations)

        self.__sessions: typing.Dict[int, TGBotWordGames.UserSessionMode] = dict()
        self.__city_game = TGBotCityGame(config, translations)

    async def process_command(self, msg: str, tg_update: Update) -> TgBotResponseType | None:
        assert(tg_update.message is not None)
        assert(tg_update.message.from_ is not None)

        lang = self.user_lang(tg_update.message.from_)

        if msg == "/reset":
            return self.reply(
                tg_update.message,
                lang.gettext('Choose a game'),
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text=lang.gettext('Cities (🇷🇺)'), callback_data='/reset-to-cities')]
                    ]
                )
            )
        return None

    async def process_message(self, tg_update: Update) -> TgBotResponseType | None:
        assert(tg_update.message is not None)
        assert(tg_update.message.from_ is not None)

        lang = self.user_lang(tg_update.message.from_)

        mode = self.__sessions.setdefault(tg_update.message.from_.id_, TGBotWordGames.UserSessionMode.null)
        if mode == TGBotWordGames.UserSessionMode.null:
            return self.reply(tg_update.message, lang.gettext('Start a game with the "/reset" command'))
        elif mode == TGBotWordGames.UserSessionMode.city:
            return await self.__city_game.process_request(tg_update)

    async def callback_query(self,  tg_update: Update) -> MethodAnswerCallbackQuery:
        assert(tg_update.callback_query is not None)

        if tg_update.callback_query.data is not None and tg_update.callback_query.from_ is not None:
            if tg_update.callback_query.data == "/reset-to-cities":
                self.__sessions[tg_update.callback_query.from_.id_] = TGBotWordGames.UserSessionMode.city
                await self.__city_game.reset(tg_update.callback_query.from_.id_, tg_update)

                lang = self.user_lang(tg_update.callback_query.from_)

                return MethodAnswerCallbackQuery(
                    callback_query_id=str(tg_update.callback_query.id_),
                    text=lang.gettext("Let's start! Name a city!"),
                    show_alert=True
                )

        return MethodAnswerCallbackQuery(callback_query_id=str(tg_update.callback_query.id_))

    @classmethod
    def bot_path(cls, config: Config) -> str:
        """Return configured path (as a part of url) for TG-bot."""
        return str(config["pyknic"]["fastapi"]["tgbot_word_games"]["url_inner_path"])
