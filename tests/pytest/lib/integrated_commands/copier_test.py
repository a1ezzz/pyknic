# -*- coding: utf-8 -*-

import asyncio
import pathlib
import typing

import pydantic
import pydantic_settings
import pytest

from pyknic.lib.capability import iscapable
from pyknic.lib.io.clients import IOClientProto
from pyknic.lib.fastapi.models.lobby import LobbyStrFeedbackResult
from pyknic.lib.integrated_commands.copier import BellBoyCopyCommand, CopierCommandModel
from fixtures.asyncio import pyknic_async_test


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


class TestBellBoyCopyCommand:

    @pyknic_async_test
    async def test_single_file_copy(
        self, module_event_loop: asyncio.AbstractEventLoop, tmp_path: pathlib.Path
    ) -> None:
        src_file = tmp_path / "source.txt"
        dst_file = tmp_path / "dest.txt"
        src_file.write_text("hello pyknic")

        model = CopierCommandModel(source=f"file://{src_file}", destination=f"file://{dst_file}")
        result = await BellBoyCopyCommand.prepare_command(model).exec()

        assert(isinstance(result, LobbyStrFeedbackResult))
        assert("copied successfully" in result.str_result)
        assert(dst_file.read_text() == "hello pyknic")

    @pyknic_async_test
    async def test_single_file_copy_to_directory(
        self, module_event_loop: asyncio.AbstractEventLoop, tmp_path: pathlib.Path
    ) -> None:
        src_file = tmp_path / "source.txt"
        dst_dir = tmp_path / "dest_dir"
        src_file.write_text("file content")
        dst_dir.mkdir()

        model = CopierCommandModel(source=f"file://{src_file}", destination=f"file://{dst_dir}")
        result = await BellBoyCopyCommand.prepare_command(model).exec()

        assert(isinstance(result, LobbyStrFeedbackResult))
        assert((dst_dir / "source.txt").read_text() == "file content")

    @pyknic_async_test
    async def test_single_file_overwrite_directory_raises(
        self, module_event_loop: asyncio.AbstractEventLoop, tmp_path: pathlib.Path
    ) -> None:
        src_file = tmp_path / "my_name"
        src_file.write_text("file content")
        dst_dir = tmp_path / "dest_dir"
        dst_dir.mkdir()
        (dst_dir / "my_name").mkdir()

        model = CopierCommandModel(source=f"file://{src_file}", destination=f"file://{dst_dir}")
        with pytest.raises(IsADirectoryError):
            await BellBoyCopyCommand.prepare_command(model).exec()

    @pyknic_async_test
    async def test_directory_copy_without_recursive_raises(
        self, module_event_loop: asyncio.AbstractEventLoop, tmp_path: pathlib.Path
    ) -> None:
        src_dir = tmp_path / "src_dir"
        src_dir.mkdir()
        (src_dir / "file.txt").write_text("content")
        dst_dir = tmp_path / "dst_dir"

        model = CopierCommandModel(
            source=f"file://{src_dir}", destination=f"file://{dst_dir}", recursive=False
        )
        with pytest.raises(IsADirectoryError):
            await BellBoyCopyCommand.prepare_command(model).exec()

    @pyknic_async_test
    async def test_recursive_copy_to_existing_directory(
        self, module_event_loop: asyncio.AbstractEventLoop, tmp_path: pathlib.Path
    ) -> None:
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "a.txt").write_text("aaa")
        (src_dir / "sub").mkdir()
        (src_dir / "sub" / "b.txt").write_text("bbb")
        (src_dir / "sub" / "nested").mkdir()
        (src_dir / "sub" / "nested" / "c.txt").write_text("ccc")
        (src_dir / "empty").mkdir()

        dst_dir = tmp_path / "dst"
        dst_dir.mkdir()

        model = CopierCommandModel(
            source=f"file://{src_dir}", destination=f"file://{dst_dir}", recursive=True
        )
        result = await BellBoyCopyCommand.prepare_command(model).exec()

        assert(isinstance(result, LobbyStrFeedbackResult))
        assert("Directory from" in result.str_result)
        assert("copied successfully" in result.str_result)
        assert((dst_dir / "a.txt").read_text() == "aaa")
        assert((dst_dir / "sub" / "b.txt").read_text() == "bbb")
        assert((dst_dir / "sub" / "nested" / "c.txt").read_text() == "ccc")
        assert((dst_dir / "empty").is_dir())

    @pyknic_async_test
    async def test_recursive_copy_to_existing_file_raises(
        self, module_event_loop: asyncio.AbstractEventLoop, tmp_path: pathlib.Path
    ) -> None:
        src_dir = tmp_path / "src_dir"
        src_dir.mkdir()
        dst_file = tmp_path / "existing.txt"
        dst_file.write_text("already a file")

        model = CopierCommandModel(
            source=f"file://{src_dir}", destination=f"file://{dst_file}", recursive=True
        )
        with pytest.raises(NotADirectoryError):
            await BellBoyCopyCommand.prepare_command(model).exec()

    @pyknic_async_test
    async def test_recursive_copy_single_file(
        self, module_event_loop: asyncio.AbstractEventLoop, tmp_path: pathlib.Path
    ) -> None:
        src_file = tmp_path / "source.txt"
        src_file.write_text("single file content")
        dst_file = tmp_path / "dest.txt"

        model = CopierCommandModel(
            source=f"file://{src_file}", destination=f"file://{dst_file}", recursive=True
        )
        result = await BellBoyCopyCommand.prepare_command(model).exec()

        assert(isinstance(result, LobbyStrFeedbackResult))
        assert("File from" in result.str_result)
        assert(dst_file.read_text() == "single file content")

    @pyknic_async_test
    async def test_copy_file_with_throttling(
        self, module_event_loop: asyncio.AbstractEventLoop, tmp_path: pathlib.Path
    ) -> None:
        src_file = tmp_path / "source.txt"
        src_file.write_text("throttled content")
        dst_file = tmp_path / "dest.txt"

        model = CopierCommandModel(
            source=f"file://{src_file}",
            destination=f"file://{dst_file}",
            throttling=1024 * 1024,
        )
        result = await BellBoyCopyCommand.prepare_command(model).exec()

        assert(isinstance(result, LobbyStrFeedbackResult))
        assert(dst_file.read_text() == "throttled content")

    @pyknic_async_test
    async def test_invalid_args_type(self, module_event_loop: asyncio.AbstractEventLoop) -> None:
        class OtherModel(pydantic.BaseModel):
            foo: str = "bar"

        with pytest.raises(TypeError):
            BellBoyCopyCommand(OtherModel())

        model = CopierCommandModel(source="file:///src", destination="file:///dst")
        cmd = BellBoyCopyCommand(model)
        cmd._args = OtherModel()
        with pytest.raises(TypeError):
            await cmd.exec()

    @pyknic_async_test
    async def test_missing_file_size_capability(
        self, module_event_loop: asyncio.AbstractEventLoop, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import pyknic.lib.integrated_commands.copier as copier_mod
        orig_iscapable = iscapable

        def mock_iscapable(target: typing.Any, cap: typing.Any, *other_caps: typing.Any) -> bool:
            if cap is IOClientProto.file_size or IOClientProto.file_size in other_caps:
                return False
            return bool(orig_iscapable(target, cap, *other_caps))

        monkeypatch.setattr(copier_mod, "iscapable", mock_iscapable)
        model = CopierCommandModel(source="file:///src", destination="file:///dst")
        with pytest.raises(ValueError):
            await BellBoyCopyCommand.prepare_command(model).exec()

    @pyknic_async_test
    async def test_missing_recursive_capability(
        self, module_event_loop: asyncio.AbstractEventLoop, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import pyknic.lib.integrated_commands.copier as copier_mod
        orig_iscapable = iscapable

        def mock_iscapable(target: typing.Any, cap: typing.Any, *other_caps: typing.Any) -> bool:
            if cap is IOClientProto.list_directory or IOClientProto.list_directory in other_caps:
                return False
            return bool(orig_iscapable(target, cap, *other_caps))

        monkeypatch.setattr(copier_mod, "iscapable", mock_iscapable)
        model = CopierCommandModel(source="file:///src", destination="file:///dst", recursive=True)
        with pytest.raises(ValueError):
            await BellBoyCopyCommand.prepare_command(model).exec()
