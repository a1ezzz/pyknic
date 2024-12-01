# -*- coding: utf-8 -*-
# pyknic/tasks/fastapi/word_games/cities.py
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
import pathlib
import random
import typing

from pyknic.lib.config import Config
from pyknic.lib.fastapi.models.tg_bot_types import Update
from pyknic.lib.fastapi.base import TgBotBaseFastAPIApp, TgBotResponseType
from pyknic.lib.gettext import GetTextWrapper
from pyknic.path import root_path


class TGBotCityGame(TgBotBaseFastAPIApp):

    __default_city_file__ = root_path / 'data' / 'cities_ru.txt'
    # Original file is made with this resource -- "https://ru.wikinews.org/wiki/Категория:Города_по_алфавиту"

    @classmethod
    def create_app(cls, fastapi_app: fastapi.FastAPI, config: Config, translations: GetTextWrapper) -> typing.Any:
        raise TypeError('This class should be created directly')

    @classmethod
    def bot_path(cls, config: Config) -> str:
        raise TypeError('This class should be created directly')

    async def tgbot_webhook_request(self, request: fastapi.Request) -> TgBotResponseType:
        raise TypeError('This class should be created directly')

    def __init__(self, config: Config, translations: GetTextWrapper):
        TgBotBaseFastAPIApp.__init__(self, config, translations)

        self.__cities: typing.Set[str] = set()
        self.__sessions: typing.Dict[int, typing.List[str]] = dict()

        self.__update_cities(self.__default_city_file__)

    def __update_cities(self, file_path: str | pathlib.Path) -> None:
        with open(file_path) as f:
            self.__cities.update((x.strip() for x in f.readlines() if len(x.strip())))

    def __allowed_city(self, city_name: str, user_id: int) -> typing.Optional[str]:
        mentioned_cities = self.__sessions[user_id]

        limited_cities = [
            x for x in self.__cities if x.startswith(city_name[-1]) and x != city_name and x not in mentioned_cities
        ]

        if len(limited_cities) > 0:
            return random.choice(limited_cities)
        elif len(limited_cities) == 0 and len(city_name) > 1:
            return self.__allowed_city(city_name[:-1], user_id)
        return None

    def reset(self, id_: int) -> None:
        self.__sessions.setdefault(id_, []).clear()

    def last_city(self, id_: int) -> str | None:
        cities = self.__sessions.setdefault(id_, [])
        if cities:
            return cities[-1]
        return None

    def process_command(self, command: str, tg_update: Update) -> TgBotResponseType | None:
        assert(tg_update.message is not None)
        assert(tg_update.message.from_ is not None)

        last_city_name = self.last_city(tg_update.message.from_.id_)
        lang = self.user_lang(tg_update.message.from_)

        if command == "/help":
            if last_city_name is None:
                return self.reply(tg_update.message, lang.gettext("Name any city you know! We have just started!"))

            city_name = self.__allowed_city(last_city_name, tg_update.message.from_.id_)
            if city_name is not None:
                return self.reply(
                    tg_update.message,
                    lang.gettext('The "%(cn)s" city is an option') % {'cn': city_name.capitalize()}
                )
            else:
                return self.reply(tg_update.message, lang.gettext('Know nothing more. One more game?'))
        elif command == "/stats":
            city_count = len(self.__sessions[tg_update.message.from_.id_])
            return self.reply(
                tg_update.message,
                lang.ngettext(
                    'We have mentioned %(cc)i city',
                    'We have mentioned %(cc)i cities',
                    city_count
                ) % {'cc': city_count}
            )

        return self.reply(tg_update.message, lang.gettext('Unknown command -- "%(c)s"') % {'c': command})

    def process_message(self, tg_update: Update) -> TgBotResponseType:
        assert(tg_update.message is not None)
        assert(tg_update.message.from_ is not None)
        assert(tg_update.message.text is not None)

        mentioned_cities = self.__sessions.setdefault(tg_update.message.from_.id_, [])
        msg = tg_update.message.text.lower().strip()

        lang = self.user_lang(tg_update.message.from_)

        if len(msg) == 0:
            return self.reply(tg_update.message, lang.gettext('Please repeat'))

        if msg not in self.__cities:
            return self.reply(
                tg_update.message,
                lang.gettext('Unknown city -- "%(cn)s"') % {'cn': msg.capitalize()}
            )

        if msg in mentioned_cities:
            return self.reply(
                tg_update.message,
                lang.gettext('The "%(cn)s" city has been mentioned already') % {'cn': msg.capitalize()}
            )

        if len(mentioned_cities) > 0:
            prev_city = mentioned_cities[-1]
            check_city = self.__allowed_city(prev_city, tg_update.message.from_.id_)

            if check_city is None:
                return self.reply(tg_update.message, lang.gettext('No more cities left. I -- loose; you -- win!'))

            if check_city[0] != msg[0]:
                return self.reply(
                    tg_update.message,
                    lang.gettext("The \"%(cn)s\" city doesn't starts with the %(l)s") % {
                        'cn': msg.capitalize(), 'l': check_city[0]
                    }
                )

        mentioned_cities.append(msg)
        answer = self.__allowed_city(msg, tg_update.message.from_.id_)

        if answer is None:
            return self.reply(tg_update.message, lang.gettext('No more cities left. I -- loose; you -- win!'))

        mentioned_cities.append(answer)
        return self.reply(tg_update.message, text=answer.capitalize())
