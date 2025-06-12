# -*- coding: utf-8 -*-
# pyknic/lib/fastapi/base.py
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

# TODO: write tests for the code

import gettext
import fastapi
import typing

from abc import abstractmethod

from pyknic.lib.config import Config
from pyknic.lib.gettext import GetTextWrapper
from pyknic.lib.fastapi.apps_registry import FastAPIAppProto
from pyknic.lib.fastapi.models.tg_bot_types import User, Message, ReplyParameters, Update
from pyknic.lib.fastapi.models.tg_bot_methods import MethodSendMessage, MethodAnswerCallbackQuery
from pyknic.lib.fastapi.models.base import NullableResponseModel


# noinspection PyAbstractClass
class BaseFastAPIApp(FastAPIAppProto):
    """ Base implementation for FastAPI apps
    """

    def __init__(self, config: Config, translations: GetTextWrapper):
        """ Create an app

        :param config: The pyknic config
        :param translations: application translation
        """
        FastAPIAppProto.__init__(self)
        self.__config = config
        self.__translations = translations

    def config(self) -> Config:
        """ Return global config
        """
        return self.__config

    def lang(self, lang_name: str | None = None) -> gettext.GNUTranslations | gettext.NullTranslations:
        """ Return translation for the specified language

        :param lang_name: a language to return (a default one will be used if this parameter is not set)
        """
        return self.__translations(lang_name)


TgBotResponseType: typing.TypeAlias = typing.Union[MethodSendMessage, MethodAnswerCallbackQuery, NullableResponseModel]


class TgBotBaseFastAPIApp(BaseFastAPIApp):
    """ Base implementation for telegram bot
    """

    @classmethod
    def create_app(cls, fastapi_app: fastapi.FastAPI, config: Config, translations: GetTextWrapper) -> typing.Any:
        """ The :meth:`.FastAPIAppProto.create_app` method implementation
        """
        app = cls(config, translations)

        # :note: response_model_exclude_unset=True excludes defaults
        # :note: null values must be excluded
        # :note: non-null defaults should be returned
        fastapi_app.post(
            cls.bot_path(config),
            status_code=200,
            response_model=TgBotResponseType,
            response_model_exclude_none=True
        )(app.tgbot_webhook_request)

        return app

    @classmethod
    @abstractmethod
    def bot_path(cls, config: Config) -> str:
        """ Return an HTTP path of webhook that this bot uses
        """
        raise NotImplementedError('This method is abstract')

    async def tgbot_webhook_request(self, request: fastapi.Request) -> TgBotResponseType:
        """ Process request from a Telegram's server. This method just parses a input and all the work is done inside
        the :meth:`.TgBotBaseFastAPIApp.process_request` method
        """
        data = await request.json()
        tg_update = Update.model_validate(data)
        return await self.process_request(tg_update)

    async def process_request(self, tg_update: Update) -> TgBotResponseType:
        """ Try to process a request. Request is processed in the following order:
          - first of all if the request has a callback_query then
          the :meth:`TgBotBaseFastAPIApp.callback_query` method result is returned
          - then if there is a message that has text and this text starts with the "/" then this message will be
          treated as a command and the :meth:`TgBotBaseFastAPIApp.process_command` method result is checked
          (if there is one, then return it)
          - then if there is a message that has text then try to process it with
          the :meth:`TgBotBaseFastAPIApp.process_message` method
          - at the end a "null" ("{}" -- empty dict) result is returned
        """
        if tg_update.callback_query is not None:
            return await self.callback_query(tg_update)  # TODO: everything else to async!

        if tg_update.message is not None and tg_update.message.text is not None and tg_update.message.from_ is not None:
            msg = tg_update.message.text.strip().lower()

            if msg.startswith('/') and len(msg) > 1:
                result = await self.process_command(msg, tg_update)
                if result is not None:
                    return result

            result = await self.process_message(tg_update)
            if result is not None:
                return result

        return NullableResponseModel()

    async def callback_query(self,  tg_update: Update) -> MethodAnswerCallbackQuery:
        """ A request treated as a callback_query -- return a default value
        """
        assert(tg_update.callback_query is not None)
        return MethodAnswerCallbackQuery(callback_query_id=str(tg_update.callback_query.id_))

    async def process_command(self, command: str, tg_update: Update) -> TgBotResponseType | None:
        """ A request is a command -- return a result if command is valid and return None otherwise
        """
        assert(tg_update.message is not None)
        assert(tg_update.message.from_ is not None)
        return None

    async def process_message(self, tg_update: Update) -> TgBotResponseType | None:
        """ A request is just a text -- try to process it
        """
        assert(tg_update.message is not None)
        assert(tg_update.message.from_ is not None)
        return None

    def user_lang(self, user: User | None = None) -> gettext.GNUTranslations | gettext.NullTranslations:
        """ Return a translation that is based on a users language
        """
        return self.lang(user.language_code if user is not None else None)

    def reply(self, tg_obj: Message | Update, text: str, **kwargs: typing.Any) -> MethodSendMessage:
        """ Shortcut for a response that replies to user's message

        :param tg_obj: original user request
        :param text: text to reply
        :param kwargs: extra parameters for the MethodSendMessage object (besides "chat_id", "text"
        and "reply_parameters" fields)
        """

        tg_msg = tg_obj if isinstance(tg_obj, Message) else tg_obj.message
        assert(tg_msg is not None)

        return MethodSendMessage(
            chat_id=tg_msg.chat.id_,
            text=text,
            reply_parameters=ReplyParameters(message_id=tg_msg.message_id),
            **kwargs
        )
