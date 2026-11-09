# -*- coding: utf-8 -*-
# pyknic/lib/bellboy.py
#
# Copyright (C) 2026 the pyknic authors and contributors
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

# TODO: document it
# TODO: test it

import asyncio
import pathlib
import threading
import typing
import sys

import pydantic
import pydantic_settings

from pyknic.environment import PyknicEnvVars, PyknicLogLevel

PyknicEnvVars.export_settings(app_name='bellboy')  # this sets up logger correctly

# TODO: import internal tasks the same way as it happens with external ones
import pyknic.lib.integrated_commands  # noqa: F401, E402  # force commands loading

from pyknic.lib.bellboy.console import BellboyConsole  # noqa: E402
from pyknic.lib.bellboy.models import CommonBellBoyCommandModel, FormattingMode  # noqa: E402
from pyknic.lib.bellboy.app import __default_bellboy_commands_registry__, BellBoyCommandHandler  # noqa: E402
from pyknic.lib.capability import iscapable  # noqa: E402
from pyknic.lib.fastapi.lobby import LobbyCommandHandler  # noqa: E402
from pyknic.lib.fastapi.models.lobby import LobbyCommandResult  # noqa: E402

from pyknic.base_app import BaseApp  # noqa: E402


# TODO: make the "rich" package optional dependency. But note! There is a direct call to the rich module inside
#  the "login" command


class BellboyApp(BaseApp):

    class BaseCommand(pydantic.BaseModel):
        bellboy: typing.Optional[CommonBellBoyCommandModel] = pydantic.Field(
            default=None,
            description='Utility configuration'
        )
        _command_handler: typing.Type[BellBoyCommandHandler]

    @classmethod
    def args_parser_cls(cls, argv: typing.Optional[typing.Sequence[str]] = None) -> pydantic_settings.BaseSettings:
        commands_annotations: typing.Dict[str, typing.Any] = dict()

        for command, handler in __default_bellboy_commands_registry__:

            if not isinstance(command, str):
                raise TypeError(f'Invalid command type -- {command.__class__}')

            handler_model: typing.Type[pydantic.BaseModel] = handler.command_model()

            class CustomModel(BellboyApp.BaseCommand, handler_model):  # type: ignore[misc,valid-type]
                """"""  # this makes __doc__ suitable for a command description

                _command_handler = handler

            cmd_description = handler.bellboy_command_description()
            if cmd_description:
                CustomModel.__doc__ = cmd_description

            commands_annotations[command] = pydantic_settings.CliSubCommand[CustomModel]  # type: ignore[misc]

        class CommandsSpec:
            __annotations__ = commands_annotations

        class BellboySettings(
            CommandsSpec,
            pydantic_settings.BaseSettings,
            cli_parse_args=(argv if argv else True),
            cli_prog_name='bellboy',
            cli_use_class_docs_for_groups=True,
            cli_exit_on_error=False
        ):
            """ Standalone pyknic tool and a client for the pyknic server
            """
            pass

        return BellboySettings()

    def __init__(
        self,
        log_level: PyknicLogLevel = PyknicLogLevel.INFO,
        config_file: typing.Optional[str] = None,
        config_dir: typing.Optional[str] = None,
        argv: typing.Optional[typing.Sequence[str]] = None
    ):
        BaseApp.__init__(self, log_level=log_level, config_file=config_file, config_dir=config_dir)
        self.__argv = argv
        self.__loop_thread: typing.Optional[threading.Thread] = None
        self.__started_cmd: typing.Optional[LobbyCommandHandler] = None
        self.__stop_request_future: typing.Optional[asyncio.Future[typing.Coroutine[None, None, None]]] = None

    def terminate(self) -> None:
        if not self.instance_lock().locked():
            raise RuntimeError('This method should be called under the lock!')

        if self.__loop_thread is not threading.current_thread():
            # Current implementation will be executed in a main thread, so as:
            #   - BellBoyApp code
            #   - AsyncIO-loop inside a BellBoyApp code
            #   - terminate-request from the signal handler
            #   - BaseApp.stop method
            # In a future, when there will be a case to call this method from other thread, this method
            # will be updated.
            raise RuntimeError('This method must be called from the main thread only!')

        if self.__started_cmd and self.__stop_request_future and not self.__stop_request_future.done():

            if iscapable(self.__started_cmd, LobbyCommandHandler.terminate_command):
                coro = self.__started_cmd.terminate_command()
                self.__stop_request_future.set_result(coro)

        BaseApp.stop(self)

    async def __main_coro(
        self, loop: asyncio.AbstractEventLoop, command: LobbyCommandHandler
    ) -> typing.Optional[LobbyCommandResult]:

        async def stop_request_coro() -> None:
            assert(self.__stop_request_future)
            term_cmd_coro = await self.__stop_request_future
            await term_cmd_coro

        command_task = asyncio.create_task(command.exec(), name='pyknic:bellboy:command-task')
        future_cancel_task = asyncio.create_task(stop_request_coro(), name='pyknic:bellboy:future_cancel_task')
        done, pending = await asyncio.wait([command_task, future_cancel_task], return_when=asyncio.FIRST_COMPLETED)

        for i in pending:
            i.cancel()

        if command_task in done:
            return command_task.result()

        return None

    def start(self) -> None:
        if self.__loop_thread:
            raise RuntimeError('This app has been started already! Unable to run twice')

        BaseApp.start(self)

        try:

            tasks_source = self.tasks_source()
            tasks_source.execute('plugins_task')
            tasks_source.wait_for(tasks_source.datalog(), 'plugins_task')

            config_result = tasks_source.wait_for(tasks_source.datalog(), 'config_task')
            config = config_result.result  # type: ignore[union-attr]

            console = BellboyConsole()

            try:
                cmd = self.args_parser_cls(self.__argv)
            except pydantic.ValidationError as e:
                console.error(str(e))
                raise SystemExit(-1)

            subcommand_obj = pydantic_settings.get_subcommand(cmd)
            if subcommand_obj is None:
                raise RuntimeError('Unable to find a subcommand')

            if not isinstance(subcommand_obj, BellboyApp.BaseCommand):
                raise TypeError(f'Invalid subcommand type -- {subcommand_obj.__class__}')

            if subcommand_obj.bellboy is not None:
                if subcommand_obj.bellboy.config is not None:
                    with pathlib.Path().open(subcommand_obj.bellboy.config) as f:
                        config.merge_file(f)

            loop = asyncio.new_event_loop()

            with self.instance_lock():
                self.__stop_request_future = loop.create_future()
                self.__loop_thread = threading.current_thread()
                self.__started_cmd = subcommand_obj._command_handler.prepare_command(subcommand_obj)

            result = loop.run_until_complete(self.__main_coro(loop, self.__started_cmd))

            if result is None:
                # this was a ctrl-c a-like request
                sys.exit(-1)

            json_mode = False
            if subcommand_obj.bellboy is not None:
                if subcommand_obj.bellboy.formatting is not None:
                    if subcommand_obj.bellboy.formatting == FormattingMode.json:
                        json_mode = True
                    else:
                        if subcommand_obj.bellboy.formatting != FormattingMode.rich:
                            raise RuntimeError('Unknown formatting settings spotted')

            if json_mode:
                print(result.model_dump_json())
            else:
                console.process_result(result)

        finally:
            self.stop()

    @classmethod
    def main(cls, argv: typing.Optional[typing.Sequence[str]] = None) -> int:
        # TODO: custom verbosity levels!
        bellboy_app = BellboyApp(argv=argv, log_level=PyknicLogLevel.INFO)
        bellboy_app.setup_singals_handler()
        bellboy_app.start()

        return 0


if __name__ == "__main__":
    sys.exit(BellboyApp.main())
