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

import asyncio
import random
import typing

import aiohttp
import decorator
import pydantic_core
import pytest

from pyknic.lib.fastapi.models.tg_bot_types import Message, Chat, User, Update
from pyknic.lib.fastapi.models.tg_bot_methods import MethodSendMessage

from fixture_helpers import pyknic_fixture, BaseFixture


class TGFixture(BaseFixture):

    def __init__(self) -> None:
        self.user = User(id_=random.randint(10000, 15000))  # type: ignore[call-arg]
        self.chat = Chat(id_=random.randint(20000, 25000), type_="private")  # type: ignore[call-arg]
        self.next_update_id = random.randint(30000, 35000)
        self.next_message_id = random.randint(40000, 45000)
        self.handler_path: typing.Optional[str] = None

    def __next_update_id(self) -> int:
        result = self.next_update_id
        self.next_update_id += 1
        return result

    def __next_message_id(self) -> int:
        result = self.next_message_id
        self.next_message_id += 1
        return result

    async def request(self, text: str, *, handler_path: typing.Optional[str] = None) -> aiohttp.ClientResponse:
        msg = Update(
            update_id=self.__next_update_id(),
            message=Message(  # type: ignore[call-arg]
                message_id=self.__next_message_id(),
                from_=self.user,
                chat=self.chat,
                text=text
            )
        )

        if handler_path is None:
            handler_path = self.handler_path

            if handler_path is None:
                raise ValueError('Handler path is not set')

        session = aiohttp.ClientSession()
        return await session.post(
            f'http://localhost:8000/{handler_path}',
            json=msg.model_dump(exclude_none=True, by_alias=True)
        )

    async def tg_response_to(self, text: str, *, handler_path: typing.Optional[str] = None) -> MethodSendMessage:
        response = await self.request(text, handler_path=handler_path)
        assert(response.status == 200)
        data = await response.text()
        return MethodSendMessage.model_validate(pydantic_core.from_json(data, allow_partial=True))

    @classmethod
    def start(cls) -> typing.Any:
        return TGFixture()

    @staticmethod
    def tg_setup(
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
                    if isinstance(i, TGFixture):
                        fixture_found = True
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
def tgbot_fixture() -> typing.Generator[TGFixture, None, None]:
    yield from pyknic_fixture(TGFixture)
