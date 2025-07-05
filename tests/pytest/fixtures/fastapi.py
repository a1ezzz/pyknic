
import asyncio
import io
import typing
import warnings

import decorator
import fastapi
import uvicorn
import pytest

from pyknic.lib.fastapi.base import BaseFastAPIApp
from pyknic.path import root_path
from pyknic.lib.config import Config
from pyknic.lib.gettext import GetTextWrapper

from fixtures.asyncio import BaseAsyncFixture
from fixtures.event_loop import EventLoopDescriptor
from fixture_helpers import pyknic_fixture


class AsyncFastAPIFixture(BaseAsyncFixture):

    __startup_retries__ = 10
    __startup_pause__ = 0.5

    def __init__(self) -> None:
        BaseAsyncFixture.__init__(self)
        self.fastapi = fastapi.FastAPI()

        self.config = uvicorn.Config(self.fastapi)
        self.server = uvicorn.Server(self.config)

        with open(root_path / 'tasks/fastapi/config.yaml') as f:
            self.default_config = Config(file_obj=f)
        self.gettext = GetTextWrapper(root_path / 'locales')
        self.configured_with: typing.Optional[typing.Type[BaseFastAPIApp]] = None
        self.app_config = Config()

    async def start_async_service(self, loop_descriptor: EventLoopDescriptor) -> None:
        assert(not self.server.started)
        if not self.server.started:

            with warnings.catch_warnings():
                # TODO: check deprecation that uvicorn produce
                warnings.filterwarnings("ignore", category=DeprecationWarning, message="websockets.legacy")
                warnings.filterwarnings(
                    "ignore", category=DeprecationWarning, message="websockets.server.WebSocketServerProtocol"
                )
                await self.server.serve()

    async def wait_startup(self, loop_descriptor: EventLoopDescriptor) -> None:
        for _ in range(self.__startup_retries__):
            if self.server.started:
                break
            await asyncio.sleep(self.__startup_pause__)
        assert(self.server.started)

    async def flush_async(self, loop_descriptor: EventLoopDescriptor) -> None:
        self.fastapi.routes.clear()
        self.configured_with = None

    async def stop_async(self) -> None:
        self.server.should_exit = True
        await self.server.shutdown()

    def setup_fastapi(
        self, fast_api_cls: typing.Type[BaseFastAPIApp], extra_config: str | None = None
    ) -> None:
        if self.configured_with is None:
            self.configured_with = fast_api_cls

            self.app_config = Config()
            self.app_config.merge_config(self.default_config)
            if extra_config:
                self.app_config.merge_config(Config(file_obj = io.StringIO(extra_config)))

            fast_api_cls.create_app(self.fastapi, self.app_config, self.gettext)
        elif self.configured_with is not fast_api_cls:
            raise ValueError('Already configured fixture!')

    @staticmethod
    def base_config(
        fast_api_cls: typing.Type[BaseFastAPIApp],
        extra_config: str | None = None,
    ) -> typing.Callable[..., typing.Any]:

        def first_level_decorator(
            decorated_function: typing.Callable[..., typing.Any]
        ) -> typing.Callable[..., typing.Any]:
            def second_level_decorator(
                original_function: typing.Callable[..., typing.Any], *args: typing.Any, **kwargs: typing.Any
            ) -> typing.Any:

                fixture_found = False
                for i in args:
                    if isinstance(i, AsyncFastAPIFixture):
                        if fixture_found:
                            raise RuntimeError('Multiple AsyncFastAPIFixture instances found!')

                        fixture_found = True
                        i.setup_fastapi(fast_api_cls, extra_config=extra_config)

                if not fixture_found:
                    raise RuntimeError('No suitable fixture found')

                return original_function(*args, **kwargs)

            return decorator.decorator(second_level_decorator)(decorated_function)
        return first_level_decorator


def _fastapi_fixture() -> typing.Generator[AsyncFastAPIFixture, None, None]:
    yield from pyknic_fixture(AsyncFastAPIFixture)


@pytest.fixture
def fastapi_fixture() -> typing.Generator[AsyncFastAPIFixture, None, None]:
    yield from _fastapi_fixture()


@pytest.fixture(scope='class')
def fastapi_class_fixture() -> typing.Generator[AsyncFastAPIFixture, None, None]:
    yield from _fastapi_fixture()


@pytest.fixture(scope='module')
def fastapi_module_fixture() -> typing.Generator[AsyncFastAPIFixture, None, None]:
    yield from _fastapi_fixture()


@pytest.fixture(scope='package')
def fastapi_package_fixture() -> typing.Generator[AsyncFastAPIFixture, None, None]:
    yield from _fastapi_fixture()


@pytest.fixture(scope='session')
def fastapi_session_fixture() -> typing.Generator[AsyncFastAPIFixture, None, None]:
    yield from _fastapi_fixture()
