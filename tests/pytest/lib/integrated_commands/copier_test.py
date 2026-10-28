# -*- coding: utf-8 -*-

import typing

import pydantic_settings

from pyknic.lib.integrated_commands.copier import BellBoyCopyCommand, CopierCommandModel


class TestCopierCommandModel:

    def test_command_model(self) -> None:
        assert(len(BellBoyCopyCommand.command_name()) > 0)
        assert(BellBoyCopyCommand.command_model() is CopierCommandModel)

    def test_model_defaults(self) -> None:
        model = CopierCommandModel(source="file:///src.txt", destination="file:///dst.txt")
        assert(model.source == "file:///src.txt")
        assert(model.destination == "file:///dst.txt")
        assert(model.throttling is None)
        assert(model.recursive is False)

    def test_recursive_options(self) -> None:
        model = CopierCommandModel(
            source="file:///src",
            destination="file:///dst",
            recursive=True
        )
        assert(model.recursive is True)

    def test_cli_mutual_exclusion(self) -> None:
        class Settings(pydantic_settings.BaseSettings, cli_parse_args=True, cli_exit_on_error=False):
            copier: pydantic_settings.CliSubCommand[CopierCommandModel]

        src: pydantic_settings.CliSettingsSource[typing.Any] = pydantic_settings.CliSettingsSource(
            Settings, cli_parse_args=[]
        )

        parsed_args = src.root_parser.parse_args(['copier', '--source', 's', '--destination', 'd', '--recursive'])
        assert(hasattr(parsed_args, 'copier.recursive') is True)
        assert(getattr(parsed_args, 'copier.recursive') is True)

        parsed_args = src.root_parser.parse_args(['copier', '--source', 's', '--destination', 'd'])
        assert(hasattr(parsed_args, 'copier.recursive') is False)
