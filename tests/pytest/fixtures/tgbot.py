# -*- coding: utf-8 -*-
# tests/pytest/fixtures/tgbot.py
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

import json
import random
import typing

import aiohttp
import decorator
import pydantic
import pytest

from pyknic.lib.fastapi.base import BaseFastAPIApp, TgBotResponseType
from pyknic.lib.fastapi.models.tg_bot_types import Message, Chat, User, Update, CallbackQuery

from fixture_helpers import pyknic_fixture
from fixtures.fastapi import AsyncFastAPIFixture


class Counter:

    def __init__(self, min_value: int, max_value: int):
        self.__value = random.randint(min_value, max_value)

    def __next__(self) -> 'Counter':
        self.__value += 1
        return self

    def __int__(self) -> int:
        return self.__value

    def __str__(self) -> str:
        return str(self.__value)


class TGBotFixture(AsyncFastAPIFixture):

    def __init__(self) -> None:
        AsyncFastAPIFixture.__init__(self)
        self.user = User(id_=random.randint(10000, 15000))  # type: ignore[call-arg]
        self.chat = Chat(id_=random.randint(20000, 25000), type_="private")  # type: ignore[call-arg]

        self.update_id = Counter(30000, 35000)
        self.message_id = Counter(40000, 45000)
        self.callback_id = Counter(50000, 55000)
        self.handler_path: typing.Optional[str] = None

    async def request(
        self,
        *,
        text: typing.Optional[str] = None,
        callback_data: typing.Optional[str] = None,
        handler_path: typing.Optional[str] = None
    ) -> aiohttp.ClientResponse:
        msg = Update(
            update_id=int(next(self.update_id)),
        )

        if text:
            msg.message = Message(
                message_id=int(next(self.message_id)), from_=self.user, chat=self.chat, text=text
            )  # type: ignore[call-arg]

        if callback_data:
            msg.callback_query = CallbackQuery(
                id_=str(next(self.callback_id)), from_=self.user, data=callback_data
            )  # type: ignore[call-arg]

        if handler_path is None:
            handler_path = self.handler_path

            if handler_path is None:
                raise ValueError('Handler path is not set')

        session = aiohttp.ClientSession()
        return await session.post(
            f'http://localhost:8000/{handler_path}',
            json=msg.model_dump(exclude_none=True, by_alias=True)
        )

    async def tg_response_to(
        self,
        *,
        text: typing.Optional[str] = None,
        callback_data: typing.Optional[str] = None,
        handler_path: typing.Optional[str] = None
    ) -> TgBotResponseType:
        response = await self.request(text=text, callback_data=callback_data, handler_path=handler_path)
        assert(response.status == 200)

        data = await response.text()
        json_data = json.loads(data)
        return pydantic.TypeAdapter(TgBotResponseType).validate_python(json_data)

    @classmethod
    def start(cls) -> typing.Any:
        return TGBotFixture()

    @staticmethod
    def tg_setup(
        fast_api_cls: typing.Type[BaseFastAPIApp],
        *,
        chat: typing.Optional[typing.Dict[str, typing.Any]] = None,
        user: typing.Optional[typing.Dict[str, typing.Any]] = None,
        handler_path: typing.Optional[str] = None
    ) -> typing.Callable[..., typing.Any]:

        def first_level_decorator(
            decorated_function: typing.Callable[..., typing.Any]
        ) -> typing.Callable[..., typing.Any]:
            def second_level_decorator(
                original_function: typing.Callable[..., typing.Any], *args: typing.Any, **kwargs: typing.Any
            ) -> typing.Any:

                fixture_found = False
                for i in args:
                    if isinstance(i, TGBotFixture):

                        if fixture_found:
                            raise RuntimeError('Multiple TGBotFixture instances found!')

                        fixture_found = True

                        i.setup_fastapi(fast_api_cls)

                        if handler_path is not None:
                            i.handler_path = handler_path
                        if user is not None:
                            for key, value in user.items():
                                setattr(i.user, key, value)
                        if chat is not None:
                            for key, value in chat.items():
                                setattr(i.chat, key, value)
                        break

                if not fixture_found:
                    raise RuntimeError('No suitable fixture found')

                return original_function(*args, **kwargs)

            return decorator.decorator(second_level_decorator)(decorated_function)
        return first_level_decorator


@pytest.fixture
def tgbot_fixture() -> typing.Generator[TGBotFixture, None, None]:
    yield from pyknic_fixture(TGBotFixture)
