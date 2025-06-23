
import asyncio
import fastapi
import uvicorn
import pytest
import typing
import warnings

from fixtures.asyncio import BaseAsyncFixture
from fixture_helpers import pyknic_fixture


class AsyncFastAPIFixture(BaseAsyncFixture):

    __startup_retries__ = 10
    __startup_pause__ = 0.5

    def __init__(self) -> None:
        BaseAsyncFixture.__init__(self)
        self.fastapi = fastapi.FastAPI()

        self.config = uvicorn.Config(self.fastapi)
        self.server = uvicorn.Server(self.config)

    async def start_async_service(self, loop_descriptor):
        assert(not self.server.started)
        if not self.server.started:

            with warnings.catch_warnings():
                # TODO: check deprecation that uvicorn produce
                warnings.filterwarnings("ignore", category=DeprecationWarning, message="websockets.legacy")
                warnings.filterwarnings(
                    "ignore", category=DeprecationWarning, message="websockets.server.WebSocketServerProtocol"
                )
                await self.server.serve()

    async def wait_startup(self, loop_descriptor):
        for _ in range(self.__startup_retries__):
            if self.server.started:
                break
            await asyncio.sleep(self.__startup_pause__)
        assert(self.server.started)

    async def flush_async(self, loop_descriptor):
        self.fastapi.routes.clear()

    async def stop_async(self):
        self.server.should_exit = True
        await self.server.shutdown()


def _fastapi_fixture() -> typing.Generator[asyncio.AbstractEventLoop, None, None]:
    yield from pyknic_fixture(AsyncFastAPIFixture)


@pytest.fixture
def fastapi_fixture() -> typing.Generator[asyncio.AbstractEventLoop, None, None]:
    yield from _fastapi_fixture()


@pytest.fixture(scope='class')
def fastapi_class_fixture() -> typing.Generator[asyncio.AbstractEventLoop, None, None]:
    yield from _fastapi_fixture()


@pytest.fixture(scope='module')
def fastapi_module_fixture() -> typing.Generator[asyncio.AbstractEventLoop, None, None]:
    yield from _fastapi_fixture()


@pytest.fixture(scope='package')
def fastapi_package_fixture() -> typing.Generator[asyncio.AbstractEventLoop, None, None]:
    yield from _fastapi_fixture()


@pytest.fixture(scope='session')
def fastapi_session_fixture() -> typing.Generator[asyncio.AbstractEventLoop, None, None]:
    yield from _fastapi_fixture()
