# -*- coding: utf-8 -*-

import asyncio
import pytest
import threading
import typing

from fixture_helpers import BaseFixture, pyknic_fixture


class EventLoopDescriptor:

    def __init__(self, loop: asyncio.AbstractEventLoop):
        self.loop = loop
        self.__aio_fixtures: typing.Set[typing.Awaitable[typing.Any]] = set()

    def add(self, task: typing.Awaitable[typing.Any]) -> None:
        self.__aio_fixtures.add(task)

    def wait(self, task: typing.Awaitable[typing.Any]) -> None:
        self.__aio_fixtures.remove(task)
        self.loop.run_until_complete(task)

    async def __wait_all(self) -> None:
        for t in self.__aio_fixtures:
            await t
        self.__aio_fixtures.clear()

    def close(self) -> None:
        self.loop.run_until_complete(self.__wait_all())
        self.loop.close()


class EventLoop(BaseFixture):

    __loop_lock__ = threading.Lock()
    __loops__: typing.Dict[threading.Thread, EventLoopDescriptor] = dict()

    @staticmethod
    def loop(*, init_loop: bool = False) -> EventLoopDescriptor:
        with EventLoop.__loop_lock__:
            if init_loop:
                assert(threading.current_thread() not in EventLoop.__loops__)
                result_loop = EventLoopDescriptor(asyncio.new_event_loop())
                EventLoop.__loops__[threading.current_thread()] = result_loop
                return result_loop
            else:
                assert(threading.current_thread() in EventLoop.__loops__)
                return EventLoop.__loops__[threading.current_thread()]

    @staticmethod
    def close_loop() -> None:
        with EventLoop.__loop_lock__:
            assert(threading.current_thread() in EventLoop.__loops__)
            loop_descriptor = EventLoop.__loops__.pop(threading.current_thread())
        loop_descriptor.close()

    @classmethod
    def start(cls) -> typing.Any:
        return EventLoop.loop(init_loop=True)

    @classmethod
    def finalize(cls, start_result: typing.Any) -> None:
        EventLoop.close_loop()


def _event_loop() -> typing.Generator[asyncio.AbstractEventLoop, None, None]:
    yield from pyknic_fixture(EventLoop)


@pytest.fixture
def event_loop() -> typing.Generator[asyncio.AbstractEventLoop, None, None]:
    yield from _event_loop()


@pytest.fixture(scope='class')
def class_event_loop() -> typing.Generator[asyncio.AbstractEventLoop, None, None]:
    yield from _event_loop()


@pytest.fixture(scope='module')
def module_event_loop() -> typing.Generator[asyncio.AbstractEventLoop, None, None]:
    yield from _event_loop()


@pytest.fixture(scope='package')
def package_event_loop() -> typing.Generator[asyncio.AbstractEventLoop, None, None]:
    yield from _event_loop()


@pytest.fixture(scope='session')
def session_event_loop() -> typing.Generator[asyncio.AbstractEventLoop, None, None]:
    yield from _event_loop()
