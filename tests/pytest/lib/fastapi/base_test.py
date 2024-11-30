# -*- coding: utf-8 -*-

import aiohttp
import asyncio
import fastapi
import json
import pydantic_core
import pytest
import typing

from asyncio_helpers import pyknic_async_test

if typing.TYPE_CHECKING:
    # noinspection PyUnresolvedReferences
    from conftest import AsyncFastAPIFixture

from pyknic.lib.fastapi.base import BaseFastAPIApp, TgBotBaseFastAPIApp
from pyknic.lib.fastapi.models import tg_bot_types, tg_bot_methods, base as base_models
from pyknic.lib.config import Config
from pyknic.lib.gettext import GetTextWrapper
from pyknic.path import root_path


class TestBaseFastAPIApp:

    @pyknic_async_test
    async def test_abstract(
        self,
        module_event_loop: asyncio.AbstractEventLoop,
        fastapi_module_fixture: 'AsyncFastAPIFixture',
        gettext: GetTextWrapper
    ) -> None:
        pytest.raises(TypeError, BaseFastAPIApp, Config(), gettext)
        pytest.raises(NotImplementedError, BaseFastAPIApp.create_app, fastapi_module_fixture.fastapi, Config(), gettext)

    @pyknic_async_test
    async def test_sample(
        self,
        module_event_loop: asyncio.AbstractEventLoop,
        fastapi_module_fixture: 'AsyncFastAPIFixture',
        gettext: GetTextWrapper
    ) -> None:

        class SampleApp(BaseFastAPIApp):

            async def root(self, req: fastapi.Request) -> typing.Dict[str, int]:
                return {"foo": 1}

            @classmethod
            def create_app(
                cls, fastapi_app: fastapi.FastAPI, config: Config, translations: GetTextWrapper
            ) -> typing.Any:
                app = cls(config, translations)

                fastapi_app.get(
                    '/sample/app',
                    status_code=200,
                )(app.root)

                return app

        config = Config()
        app = SampleApp.create_app(fastapi_module_fixture.fastapi, config, gettext)

        assert(app.config() is config)
        assert(app.lang('en').gettext("Choose a game") == "Choose a game")
        assert(app.lang('fr').gettext("Choose a game") == "Choose a game")
        assert(app.lang('ru').gettext("Choose a game") == "Выбирай игру")

        async with aiohttp.request('get', 'http://localhost:8000/unknow/path') as response:
            assert(response.status == 404)

        async with aiohttp.request('get', 'http://localhost:8000/sample/app') as response:
            assert(response.status == 200)
            data = await response.text()
            assert(json.loads(data) == {"foo": 1})


class TestTgBotBaseFastAPIApp:

    @pyknic_async_test
    async def test_abstract(
        self,
        module_event_loop: asyncio.AbstractEventLoop,
        fastapi_module_fixture: 'AsyncFastAPIFixture',
        gettext: GetTextWrapper
    ):
        pytest.raises(TypeError, TgBotBaseFastAPIApp, Config(), gettext)
        pytest.raises(NotImplementedError, TgBotBaseFastAPIApp.bot_path, Config())

    @pyknic_async_test
    async def test_sample(
        self,
        module_event_loop: asyncio.AbstractEventLoop,
        fastapi_module_fixture: 'AsyncFastAPIFixture',
        gettext: GetTextWrapper
    ):

        class SampleBot(TgBotBaseFastAPIApp):

            @classmethod
            def bot_path(cls, config: Config) -> str:
                return '/smart/bot'

            def process_message(
                self, tg_update: tg_bot_types.Update
            ) -> tg_bot_methods.MethodSendMessage | base_models.NullableResponseModel | None:
                if tg_update.message.text != 'Hello!':
                    return self.reply(tg_update, tg_update.message.text)

        config = Config()
        translations = GetTextWrapper(root_path / 'locales')
        app = SampleBot.create_app(fastapi_module_fixture.fastapi, config, translations)

        request1 = tg_bot_types.Update(
            update_id=1,
            message=tg_bot_types.Message(
                message_id=20,
                from_=tg_bot_types.User(id_=300),
                chat=tg_bot_types.Chat(id_=4000, type_="private"),
                text="Hello!"
            )
        )

        async with (aiohttp.request(
            'post',
            'http://localhost:8000/smart/bot',
            json=request1.model_dump(exclude_none=True, by_alias=True)
        ) as response):
            assert(response.status == 200)
            data = await response.text()
            assert(json.loads(data) == dict())

        request2 = tg_bot_types.Update(
            update_id=2,
            message=tg_bot_types.Message(
                message_id=30,
                from_=tg_bot_types.User(id_=400),
                chat=tg_bot_types.Chat(id_=5000, type_="private"),
                text="Who are you?"
            )
        )

        async with (aiohttp.request(
            'post',
            'http://localhost:8000/smart/bot',
            json=request2.model_dump(exclude_none=True, by_alias=True)
        ) as response):
            assert(response.status == 200)
            data = await response.text()
            assert(json.loads(data)['method'] == "sendMessage")  # defaults check

            bot_response = tg_bot_methods.MethodSendMessage.model_validate(
                pydantic_core.from_json(data, allow_partial=True)
            )
            assert(bot_response.method == "sendMessage")
            assert(bot_response.reply_parameters.message_id == 30)
            assert(bot_response.text == 'Who are you?')

        assert(app.user_lang(tg_bot_types.User(id_=500)).gettext("Choose a game") == "Choose a game")
        assert(
            app.user_lang(tg_bot_types.User(id_=500, language_code='fr')).gettext("Choose a game") == "Choose a game"
        )
        assert(
            app.user_lang(tg_bot_types.User(id_=500, language_code='ru')).gettext("Choose a game") == "Выбирай игру"
        )
