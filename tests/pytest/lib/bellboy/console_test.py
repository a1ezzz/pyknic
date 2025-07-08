
import pytest
import typing

if typing.TYPE_CHECKING:
    from pathlib import Path
    from _pytest.capture import CaptureFixture
    from _pytest.monkeypatch import MonkeyPatch

from pyknic.lib.fastapi.models.lobby import LobbyStrFeedbackResult, LobbyKeyValueFeedbackResult
from pyknic.lib.fastapi.models.base import NullableResponseModel
from pyknic.lib.bellboy.console import BellboyConsole, BellboyPromptParser
from pyknic.lib.bellboy.error import BellboyCLIError


class TestBellboyConsole:

    @classmethod
    def input_patch(cls, msg: str) -> typing.Callable[[typing.Any], str]:
        def patched_input(*args: typing.Any, **kwargs: typing.Any) -> str:
            return msg

        return patched_input

    def test_ask(self, capsys: 'CaptureFixture[typing.Any]', monkeypatch: 'MonkeyPatch') -> None:
        console = BellboyConsole(enable_history=False)
        monkeypatch.setattr('builtins.input', TestBellboyConsole.input_patch("foo"))
        result = console.ask('bar')
        assert('bar' in capsys.readouterr().out)
        assert(result == 'foo')

    def test_log(self, capsys: 'CaptureFixture[typing.Any]') -> None:
        console = BellboyConsole(enable_history=False)
        msg = 'some random message'
        console.log(msg)
        assert(msg in capsys.readouterr().out)

    def test_critical(self, capsys: 'CaptureFixture[typing.Any]') -> None:
        console = BellboyConsole(enable_history=False)
        msg = 'some random message'

        assert(capsys.readouterr().out == '')
        with pytest.raises(BellboyCLIError):
            try:
                raise BellboyCLIError(msg)
            except BellboyCLIError as e:
                console.critical(e)

        assert(msg in capsys.readouterr().out)

    def test_error(self, capsys: 'CaptureFixture[typing.Any]') -> None:
        console = BellboyConsole(enable_history=False)
        msg = 'some random message'
        console.error(msg)
        assert(msg in capsys.readouterr().out)

    def test_str_feedback(self, capsys: 'CaptureFixture[typing.Any]') -> None:
        console = BellboyConsole(enable_history=False)
        msg = 'some random message'
        console.str_feedback(LobbyStrFeedbackResult(str_result=msg))
        assert(msg in capsys.readouterr().out)

    def test_null_feedback(self, capsys: 'CaptureFixture[typing.Any]') -> None:
        console = BellboyConsole(enable_history=False)
        console.null_feedback(NullableResponseModel())
        assert(len(capsys.readouterr().out) > 0)

    def test_kv_feedback(self, capsys: 'CaptureFixture[typing.Any]') -> None:
        console = BellboyConsole(enable_history=False)

        msg = {'foo': 'bar'}

        console.kv_feedback(LobbyKeyValueFeedbackResult(kv_result=msg))
        captured_out = capsys.readouterr().out
        assert('foo' in captured_out)
        assert('bar' in captured_out)


class TestBellboyConsoleHistory:

    def test_history(self, capsys: 'CaptureFixture[typing.Any]', monkeypatch: 'MonkeyPatch', tmp_path: 'Path') -> None:
        hist_file = tmp_path / 'history'
        hist_file.touch()

        class CustomBellboyConsole(BellboyConsole):

            @classmethod
            def history_file_path(cls) -> str:
                return str(hist_file)

        console = CustomBellboyConsole()

        assert(open(hist_file).read() == '')

        monkeypatch.setattr('builtins.input', TestBellboyConsole.input_patch("foo"))
        console.ask('bar')
        assert('bar' in capsys.readouterr().out)

        assert(open(hist_file).read() == '')  # there is no flush yet

        console.commit_history()
        assert(open(hist_file).read() == '')  # there is no flush yet

        with pytest.raises(ValueError):
            console.commit_history()  # there wasn't extra ask call

        console.dump_history()
        assert(open(hist_file).read() == 'foo\n')  # there is a flush!


class TestBellboyPromptParser:

    def test_plain(self) -> None:
        prompt_parser = BellboyPromptParser('do', tuple())
        assert(prompt_parser.command() == 'do')
        assert(prompt_parser.args() is None)
        assert(prompt_parser.kwargs() is None)
        assert(prompt_parser.cargs() is None)

    def test_args(self) -> None:
        prompt_parser = BellboyPromptParser('do 1 2 foo', tuple())
        assert(prompt_parser.command() == 'do')
        assert(prompt_parser.args() == ('1', '2', 'foo'))
        assert(prompt_parser.kwargs() is None)
        assert(prompt_parser.cargs() is None)

    def test_kwargs(self) -> None:
        prompt_parser = BellboyPromptParser('do --some value', tuple())
        assert(prompt_parser.command() == 'do')
        assert(prompt_parser.args() is None)
        assert(prompt_parser.kwargs() == {'some': 'value'})
        assert(prompt_parser.cargs() is None)

    def test_cargs(self) -> None:
        prompt_parser = BellboyPromptParser('do --some value', ('some', ))
        assert(prompt_parser.command() == 'do')
        assert(prompt_parser.args() is None)
        assert(prompt_parser.kwargs() is None)
        assert(prompt_parser.cargs() == {'some': 'value'})

    def test_multiple_args(self) -> None:
        prompt_parser = BellboyPromptParser('do --some value --other 1 2 3 4 "foo bar"', ('some', ))
        assert(prompt_parser.command() == 'do')
        assert(prompt_parser.args() == ("2", "3", "4", "foo bar"))
        assert(prompt_parser.kwargs() == {'other': '1'})
        assert(prompt_parser.cargs() == {'some': 'value'})

    def test_exceptions(self) -> None:
        with pytest.raises(BellboyCLIError):
            BellboyPromptParser('do --', tuple())

        with pytest.raises(BellboyCLIError):
            BellboyPromptParser('do --foo', tuple())
