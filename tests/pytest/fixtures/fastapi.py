
import asyncio
import fastapi
import pytest
import uvicorn
import typing

from asyncio_helpers import BaseAsyncFixture, async_fixture_generator


class AsyncFastAPIFixture(BaseAsyncFixture):

    def __init__(self) -> None:
        BaseAsyncFixture.__init__(self)
        self.fastapi = fastapi.FastAPI()
        self.config = uvicorn.Config(self.fastapi)
        self.server = uvicorn.Server(self.config)

        self.__server_task: typing.Awaitable[typing.Any] | None = None

    async def _init_fixture(self) -> None:
        self.__server_task = asyncio.create_task(self.server.serve())

    async def __fin(self) -> None:
        assert(self.__server_task is not None)

        self.server.should_exit = True
        await self.server.shutdown()
        await self.__server_task

    def finalize(self) -> None:
        assert(self.loop is not None)
        self.loop.run_until_complete(self.__fin())


fastapi_fixture = async_fixture_generator(AsyncFastAPIFixture)
fastapi_class_fixture = async_fixture_generator(AsyncFastAPIFixture, scope="class")
fastapi_module_fixture = async_fixture_generator(AsyncFastAPIFixture, scope="module")
fastapi_package_fixture = async_fixture_generator(AsyncFastAPIFixture, scope="package")
fastapi_session_fixture = async_fixture_generator(AsyncFastAPIFixture, scope="session")
