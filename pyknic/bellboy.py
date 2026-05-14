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
import typing

import pydantic
import pydantic_settings

from pyknic.environment import PyknicEnvVars, PyknicLogLevel

PyknicEnvVars.export_settings(app_name='bellboy')  # this sets up logger correctly

import pyknic.lib.integrated_commands  # noqa: F401, E402  # force commands loading

from pyknic.lib.bellboy.console import BellboyConsole  # noqa: E402
from pyknic.lib.bellboy.models import CommonBellBoyCommandModel, FormattingMode  # noqa: E402
from pyknic.lib.bellboy.app import __default_bellboy_commands_registry__, BellBoyCommandHandler  # noqa: E402

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
    def args_parser_cls(cls) -> pydantic_settings.BaseSettings:
        commands_annotations: typing.Dict[str, typing.Any] = dict()

        for command, handler in __default_bellboy_commands_registry__:
            assert(isinstance(command, str))
            handler_model: typing.Type[pydantic.BaseModel] = handler.command_model()

            class CustomModel(BellboyApp.BaseCommand, handler_model):  # type: ignore[misc,valid-type]
                _command_handler = handler

            commands_annotations[command] = pydantic_settings.CliSubCommand[CustomModel]  # type: ignore[misc]

        class CommandsSpec:
            __annotations__ = commands_annotations

        class BellboySettings(
            CommandsSpec,
            pydantic_settings.BaseSettings,
            cli_parse_args=True,
            cli_prog_name='bellboy',
            cli_use_class_docs_for_groups=True,
            cli_exit_on_error=False
        ):
            """ Standalone pyknic tool and a client for the pyknic server
            """
            pass

        return BellboySettings()

    def start(self) -> None:

        BaseApp.start(self)

        try:
            tasks_source = self.tasks_source()
            tasks_source.execute('plugins_task')
            tasks_source.wait_for(tasks_source.datalog(), 'plugins_task')

            config_result = tasks_source.wait_for(tasks_source.datalog(), 'config_task')
            config = config_result.result  # type: ignore[union-attr]

            console = BellboyConsole()

            try:
                cmd = self.args_parser_cls()
            except pydantic.ValidationError as e:
                console.error(str(e))
                raise SystemExit(-1)

            subcommand_obj = pydantic_settings.get_subcommand(cmd)
            assert(subcommand_obj is not None)

            assert(isinstance(subcommand_obj, BellboyApp.BaseCommand))
            if subcommand_obj.bellboy is not None:
                if subcommand_obj.bellboy.config is not None:
                    with pathlib.Path().open(subcommand_obj.bellboy.config) as f:
                        config.merge_file(f)

            loop = asyncio.new_event_loop()
            prepared_command = subcommand_obj._command_handler.prepare_command(subcommand_obj)
            result = loop.run_until_complete(prepared_command.exec())

            json_mode = False
            if subcommand_obj.bellboy is not None:
                if subcommand_obj.bellboy.formatting is not None:
                    if subcommand_obj.bellboy.formatting == FormattingMode.json:
                        json_mode = True
                    else:
                        assert(subcommand_obj.bellboy.formatting == FormattingMode.rich)

            if json_mode:
                print(result.model_dump_json())
            else:
                console.process_result(result)

        finally:
            self.stop()

    @classmethod
    def main(cls) -> None:
        # TODO: custom verbosity levels!

        BellboyApp.start_app('bellboy:starter', log_level=PyknicLogLevel.INFO)


if __name__ == "__main__":
    BellboyApp.main()
