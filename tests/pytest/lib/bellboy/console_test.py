
import pytest
import typing

if typing.TYPE_CHECKING:
    from _pytest.capture import CaptureFixture
    from _pytest.monkeypatch import MonkeyPatch

from pyknic.lib.bellboy.app import BellboyCLIError
from pyknic.lib.fastapi.models.lobby import LobbyStrFeedbackResult, LobbyKeyValueFeedbackResult, LobbyCommandResult
from pyknic.lib.fastapi.models.lobby import LobbyListValueFeedbackResult
from pyknic.lib.fastapi.models.base import NullableModel
from pyknic.lib.bellboy.console import BellboyConsole


class TestBellboyConsole:

    @classmethod
    def input_patch(cls, msg: str) -> typing.Callable[[typing.Any], str]:
        def patched_input(*args: typing.Any, **kwargs: typing.Any) -> str:
            return msg

        return patched_input

    def test_ask(self, capsys: 'CaptureFixture[typing.Any]', monkeypatch: 'MonkeyPatch') -> None:
        console = BellboyConsole()
        monkeypatch.setattr('builtins.input', TestBellboyConsole.input_patch("foo"))
        result = console.ask('bar')
        assert('bar' in capsys.readouterr().out)
        assert(result == 'foo')

    def test_critical(self, capsys: 'CaptureFixture[typing.Any]') -> None:
        console = BellboyConsole()
        msg = 'some random message'

        assert(capsys.readouterr().out == '')
        with pytest.raises(BellboyCLIError):
            try:
                raise BellboyCLIError(msg)
            except BellboyCLIError as e:
                console.critical(e)

        assert(msg in capsys.readouterr().out)

    def test_error(self, capsys: 'CaptureFixture[typing.Any]') -> None:
        console = BellboyConsole()
        msg = 'some random message'
        console.error(msg)
        assert(msg in capsys.readouterr().out)

    def test_str_feedback(self, capsys: 'CaptureFixture[typing.Any]') -> None:
        console = BellboyConsole()
        msg = 'some random message'
        console.str_feedback(LobbyStrFeedbackResult(str_result=msg))
        assert(msg in capsys.readouterr().out)

    def test_null_feedback(self, capsys: 'CaptureFixture[typing.Any]') -> None:
        console = BellboyConsole()
        console.null_feedback(NullableModel())
        assert(len(capsys.readouterr().out) > 0)

    def test_kv_feedback(self, capsys: 'CaptureFixture[typing.Any]') -> None:
        console = BellboyConsole()

        msg = {'foo': 'bar'}

        console.kv_feedback(LobbyKeyValueFeedbackResult(kv_result=msg))
        captured_out = capsys.readouterr().out
        assert('foo' in captured_out)
        assert('bar' in captured_out)

    def test_list_feedback(self, capsys: 'CaptureFixture[typing.Any]') -> None:
        console = BellboyConsole()

        console.list_feedback(LobbyListValueFeedbackResult(list_result=['foo', 'bar']))
        captured_out = capsys.readouterr().out
        assert('foo' in captured_out)
        assert('bar' in captured_out)

    @pytest.mark.parametrize('result', [
        NullableModel(),
        LobbyStrFeedbackResult(str_result='some string result'),
        LobbyKeyValueFeedbackResult(kv_result={'foo': 'bar', 'bar': 'foo'}),
        LobbyListValueFeedbackResult(list_result=['foo', 'bar'])
    ])
    def test_process_result(self, capsys: 'CaptureFixture[typing.Any]', result: LobbyCommandResult):
        console = BellboyConsole()
        console.process_result(result)
