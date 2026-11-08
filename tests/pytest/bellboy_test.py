
import asyncio
import json
import os
import signal
import threading
import typing

if typing.TYPE_CHECKING:
    from _pytest.capture import CaptureFixture

import pydantic
import pydantic_settings.exceptions
import pytest

from pyknic.bellboy import BellboyApp
from pyknic.lib.bellboy.app import __default_bellboy_commands_registry__
from pyknic.lib.fastapi.models.lobby import LobbyCommandResult
from pyknic.lib.fastapi.models.base import NullableModel
from pyknic.lib.bellboy.models import OptionalMainBellBoyCommandModel
from pyknic.lib.bellboy.app import BellBoyCommandHandler, register_bellboy_command


@pytest.fixture
def sleep_bellboy_command() -> typing.Generator[threading.Event, None, None]:

    readiness_event = threading.Event()

    @register_bellboy_command()
    class SleepCommand(BellBoyCommandHandler):

        def __init__(self, args: pydantic.BaseModel):
            BellBoyCommandHandler.__init__(self, args)
            self.__stop_event = asyncio.Event()

        @classmethod
        def command_name(cls) -> str:
            return "sleep"

        @classmethod
        def command_model(cls) -> typing.Type[pydantic.BaseModel]:
            return OptionalMainBellBoyCommandModel

        async def terminate_command(self) -> None:
            self.__stop_event.set()

        async def exec(self) -> LobbyCommandResult:
            async def wait_for_stop() -> None:
                await self.__stop_event.wait()

            readiness_event.set()

            async def sleep_coro() -> None:
                for i in range(60 * 5 * 10):  # 5 min
                    await asyncio.sleep(0.1)

            task1 = asyncio.create_task(wait_for_stop(), name='test-task-4-stop')
            task2 = asyncio.create_task(sleep_coro(), name='test-task-4-sleep')

            _, pending = await asyncio.wait([task1, task2], return_when=asyncio.FIRST_COMPLETED)
            for i in pending:
                i.cancel()

            return NullableModel()

    yield readiness_event
    __default_bellboy_commands_registry__.unregister(SleepCommand.command_name())


class TestBellboyApp:

    def test(self) -> None:
        code = BellboyApp.main(['ping'])
        assert(code == 0)

    def test_json(self, capsys: 'CaptureFixture[typing.Any]') -> None:
        code = BellboyApp.main(['ping', '--bellboy.formatting', 'json'])
        assert(code == 0)

        captures = capsys.readouterr()
        assert(captures.out != '')
        returned_json = json.loads(captures.out)
        assert(len(returned_json['str_result']) > 0)

    def test_unknown_cmd(self) -> None:
        with pytest.raises(pydantic_settings.exceptions.SettingsError):
            _ = BellboyApp.main(['do-some'])

    def test_sigterm(self, sleep_bellboy_command: threading.Event) -> None:

        def call_sigterm() -> None:
            sleep_bellboy_command.wait()
            os.kill(0, signal.SIGTERM)

        thread = threading.Thread(target=call_sigterm)
        thread.start()

        with pytest.raises(SystemExit):
            BellboyApp.main(['sleep'])
        thread.join()
