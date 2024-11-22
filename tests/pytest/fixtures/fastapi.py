
import asyncio
import fastapi
import pytest
import uvicorn


@pytest.fixture(scope="module")
async def __fastapi_fixture(request: pytest.FixtureRequest) -> fastapi.FastAPI:
    app = fastapi.FastAPI()
    config = uvicorn.Config(app)
    server = uvicorn.Server(config)

    loop = asyncio.get_event_loop()
    server_task = loop.create_task(server.serve())

    async def async_fin() -> None:
        server.should_exit = True
        await server.shutdown()
        await server_task

    def fin() -> None:
        loop.run_until_complete(async_fin())

    request.addfinalizer(fin)
    return app


@pytest.fixture()
def fastapi_fixture(__fastapi_fixture: fastapi.FastAPI) -> fastapi.FastAPI:

    while len(__fastapi_fixture.router.routes):
        del __fastapi_fixture.router.routes[0]

    return __fastapi_fixture
