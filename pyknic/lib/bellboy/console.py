# -*- coding: utf-8 -*-
# pyknic/lib/bellboy/console.py
#
# Copyright (C) 2025 the pyknic authors and contributors
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

import shlex
import pathlib
import readline
import typing

import rich.console
import rich.prompt
import rich.table
import rich.text

from pyknic.lib.bellboy.error import BellboyCLIError
from pyknic.lib.fastapi.models.lobby import LobbyStrFeedbackResult, LobbyKeyValueFeedbackResult
from pyknic.lib.fastapi.models.base import NullableResponseModel
from pyknic.lib.verify import verify_value


class Prompt(rich.prompt.Prompt):
    """Overrides default prompt. It must have '\n' at the end because of readline (history) behaviour."""
    prompt_suffix = '>\n'


class BellboyConsole:
    """ Wraps and unify style and behaviour"""
    # TODO: implement completer with readline.set_completer

    def __init__(self, enable_history: bool = True) -> None:
        """ Create a new console.

        :param enable_history: whether to enable history saving or not
        """

        self.__console = rich.console.Console()
        self.__last_prompt: typing.Optional[str] = None
        self.__history_enabled = enable_history

        if self.__history_enabled:
            readline.set_auto_history(False)
            readline.read_history_file(self.history_file_path())

    def ask(self, question: str | None = None, password: bool = False) -> str:
        """ Ask a user for an input

        :param question: if defined then this question will be printed before prompt
        :param password: whether prompt should echo an input or not
        """
        if question:
            self.__console.print(rich.text.Text(question))
        result = Prompt.ask(password=password)
        self.__last_prompt = result.strip()
        return self.__last_prompt

    def commit_history(self) -> None:
        """Commit last entered string. This method call must be forestalled by the :meth:`.BellboyConsole.ask` method.
        """

        if self.__history_enabled:
            if not self.__last_prompt:
                raise ValueError('No prompt was entered')
            readline.add_history(self.__last_prompt)
            self.__last_prompt = None

    def log(self, message: str) -> None:
        """Print message as a console log entry

        :param message: message to print
        """
        self.__console.log(message)

    def critical(self, raised_exception: BellboyCLIError) -> None:
        """Process raised exception -- print error message and reraise the one.

        :param raised_exception: raised exception
        """
        self.__console.print(
            rich.text.Text(f'Fatal error spotted: "{str(raised_exception)}". Quiting...', style='red bold')
        )
        raise raised_exception

    def error(self, message: str) -> None:
        """Show error message

        :param message: error message
        """
        self.__console.print(rich.text.Text(f'Error! {message}', style='red'))

    def str_feedback(self, feedback: LobbyStrFeedbackResult) -> None:
        """Process simple result.

        :param feedback: sting-based result
        """
        self.__console.print(rich.text.Text(feedback.str_result, style='bold'))

    def kv_feedback(self, feedback: LobbyKeyValueFeedbackResult) -> None:
        """Process key-value result.

        :param feedback: dictionary result
        """
        table = rich.table.Table(title='Values received')
        table.add_column('Name', style='bold')
        table.add_column('Values', style='green', justify='right')

        table_keys = list(feedback.kv_result.keys())
        table_keys.sort()

        for k in table_keys:
            table.add_row(k, str(feedback.kv_result[k]))

        self.__console.print(table)

    def null_feedback(self, feedback: NullableResponseModel) -> None:
        """Process null result.

        :param feedback: None as is =)
        """
        self.__console.print(rich.text.Text('<command succeeded without feedback>'))

    def dump_history(self) -> None:
        """Save current history."""
        if self.__history_enabled:
            readline.write_history_file(self.history_file_path())

    @classmethod
    def history_file_path(cls) -> str:
        """Return path to a history file."""
        file_path = pathlib.Path.home() / '.bellboy_history'

        if not file_path.exists():
            file_path.touch()

        return str(file_path)


class BellboyPromptParser:
    """Parser that is used in conjunction with :meth:`.BellboyConsole.ask` method."""

    @verify_value(command=lambda x: len(x) > 0)
    def __init__(self, command: str, contexts: typing.Tuple[str, ...]):
        """Parse command

        :param command: command to parse
        :param contexts: contexts that server has
        """

        tokens = shlex.split(command)

        self.__command = tokens[0]
        self.__args, self.__kwargs, self.__cargs = self.__parse_tokens(contexts, *tokens[1:])

    def command(self) -> str:
        """Return command name (ie LobbyCommandRequest.name)."""
        return self.__command

    def args(self) -> typing.Tuple[typing.Any, ...]:
        """Return command arguments (ie LobbyCommandRequest.args)."""
        return self.__args

    def kwargs(self) -> typing.Dict[str, typing.Any]:
        """Return key-word arguments (ie LobbyCommandRequest.kwargs)."""
        return self.__kwargs

    def cargs(self) -> typing.Dict[str, typing.Any]:
        """Return contextualized arguments (ie LobbyCommandRequest.cargs)."""
        return self.__cargs

    def __parse_tokens(
        self, contexts: typing.Tuple[str, ...], *tokens: str
    ) -> typing.Tuple[
        typing.Tuple[typing.Any, ...],
        typing.Dict[str, typing.Any],
        typing.Dict[str, typing.Any]
    ]:
        """Implement base logic (parse tokens)
        """
        args = []
        kwargs = dict()
        cargs = dict()

        bypass_next = False
        for i, token in enumerate(tokens):
            if bypass_next:
                bypass_next = False
                continue

            if token.startswith('--'):
                if len(token) == 2:
                    raise BellboyCLIError('Variable name is not followed by the "--"')
                token_name = token[2:]

                if i == (len(tokens) - 1):
                    raise BellboyCLIError(f'Variable value is not followed by the named argument "{token_name}"')

                token_value = tokens[i + 1]
                if token_name in contexts:
                    cargs[token_name] = token_value
                else:
                    kwargs[token_name] = token_value
                bypass_next = True
            else:
                args.append(token)

        return (  # type: ignore[return-value]  # mypy issue
            tuple(args) if args else None,
            kwargs if kwargs else None,
            cargs if cargs else None,
        )
