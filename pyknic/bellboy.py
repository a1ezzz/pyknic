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
import os
import pathlib
import sys
import typing

import pydantic
import pydantic_settings

from pyknic.lib.config import Config
from pyknic.lib.bellboy.console import BellboyConsole
from pyknic.lib.bellboy.models import CommonBellBoyCommandModel, FormattingMode
from pyknic.lib.bellboy.app import __default_bellboy_commands_registry__, BellBoyCommandHandler
from pyknic.tasks.log import LogTask

import pyknic.lib.integrated_commands  # noqa: F401  # force commands loading


# TODO: make the "rich" package optional dependency. But note! There is a direct call to the rich module inside
#  the "login" command

# TODO: think of loading external bellboy command. May be with the entry_points (think twice!)


class Bellboy:

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

            class CustomModel(Bellboy.BaseCommand, handler_model):  # type: ignore[misc,valid-type]
                _command_handler = handler

            commands_annotations[command] = pydantic_settings.CliSubCommand[CustomModel]  # type: ignore[misc]

        class CommandsSpec:
            __annotations__ = commands_annotations

        class BellboySettings(
            CommandsSpec,
            pydantic_settings.BaseSettings,
            cli_parse_args=True,
            cli_prog_name='bellboy',
            cli_use_class_docs_for_groups=True
        ):
            """ Standalone pyknic tool and a client for the pyknic server
            """
            pass

        return BellboySettings()

    @classmethod
    def main(cls) -> None:
        config = Config()  # TODO: there is no usage at the moment =(

        with (pathlib.Path(__file__).parent / 'lib' / 'bellboy' / 'config.yaml').open() as f:
            config.merge_file(f)

        console = BellboyConsole()

        try:
            cmd = cls.args_parser_cls()
        except pydantic.ValidationError as e:
            console.error(str(e))
            sys.exit(-1)

        subcommand_obj = pydantic_settings.get_subcommand(cmd)
        assert(subcommand_obj is not None)

        assert(isinstance(subcommand_obj, Bellboy.BaseCommand))
        if subcommand_obj.bellboy is not None:
            if subcommand_obj.bellboy.config is not None:
                with pathlib.Path().open(subcommand_obj.bellboy.config):
                    config.merge_file(f)

        os.environ[LogTask.__env_var_name__] = "INFO"  # possible options are: "ERROR", "WARN", "INFO", "DEBUG"
        LogTask.setup_log()

        loop = asyncio.new_event_loop()
        result = loop.run_until_complete(
            subcommand_obj._command_handler.exec(subcommand_obj)
        )

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


if __name__ == "__main__":
    Bellboy.main()
