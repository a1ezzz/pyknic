# -*- coding: utf-8 -*-

import asyncio
import pytest
import typing


def _event_loop() -> typing.Generator[asyncio.AbstractEventLoop, None, None]:
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


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
