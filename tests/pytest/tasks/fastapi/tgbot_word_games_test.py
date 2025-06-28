# -*- coding: utf-8 -*-

import asyncio


from pyknic.lib.fastapi.models.tg_bot_methods import MethodSendMessage, MethodAnswerCallbackQuery
from pyknic.tasks.fastapi.tgbot_word_games import TGBotWordGames

from fixtures.asyncio import pyknic_async_test
from fixtures.tgbot import TGBotFixture


class TestTGBotCitiesGame:

    @TGBotFixture.tg_setup(TGBotWordGames, handler_path='tgbot/word_games')
    @pyknic_async_test
    async def test(
        self,
        module_event_loop: asyncio.AbstractEventLoop,
        tgbot_fixture: TGBotFixture
    ) -> None:
        # TODO: test gettext

        original_message_id = int(tgbot_fixture.message_id)
        bot_response = await tgbot_fixture.tg_response_to(text="/reset")
        assert(isinstance(bot_response, MethodSendMessage))
        assert(bot_response.method == "sendMessage")
        assert(bot_response.reply_parameters is not None)
        assert(bot_response.reply_parameters.message_id == (original_message_id + 1))
        assert(bot_response.text == "Choose a game")

        bot_response = await tgbot_fixture.tg_response_to(callback_data="/reset-to-cities")
        assert(isinstance(bot_response, MethodAnswerCallbackQuery))
        assert(bot_response.method == "answerCallbackQuery")

        bot_response = await tgbot_fixture.tg_response_to(text="Москва")
        assert(isinstance(bot_response, MethodSendMessage))
        assert(bot_response.method == "sendMessage")
        assert(len(bot_response.text) > 0)
        assert(bot_response.text[0] == "А")

    @TGBotFixture.tg_setup(TGBotWordGames, handler_path='tgbot/word_games')
    @pyknic_async_test
    async def test_unknown_cmd(
        self,
        module_event_loop: asyncio.AbstractEventLoop,
        tgbot_fixture: TGBotFixture
    ) -> None:
        bot_response = await tgbot_fixture.tg_response_to(text="/unknown-cmd")
        assert(isinstance(bot_response, MethodSendMessage))
        assert(bot_response.method == 'sendMessage')
        assert(bot_response.text == 'Start a game with the "/reset" command')

    @TGBotFixture.tg_setup(TGBotWordGames, handler_path='tgbot/word_games')
    @pyknic_async_test
    async def test_unknown_callback(
        self,
        module_event_loop: asyncio.AbstractEventLoop,
        tgbot_fixture: TGBotFixture
    ) -> None:
        bot_response = await tgbot_fixture.tg_response_to(text="/reset")
        assert(isinstance(bot_response, MethodSendMessage))
        assert(bot_response.method == "sendMessage")
        assert(bot_response.text == "Choose a game")

        bot_response = await tgbot_fixture.tg_response_to(callback_data="/reset-to-unknown-game")
        assert(isinstance(bot_response, MethodAnswerCallbackQuery))
        assert(bot_response.method == "answerCallbackQuery")
        assert(isinstance(bot_response, MethodAnswerCallbackQuery))
        assert(bot_response.text is None)
