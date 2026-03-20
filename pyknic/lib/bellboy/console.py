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

import typing

import rich.console
import rich.padding
import rich.prompt
import rich.table
import rich.text

from pyknic.lib.bellboy.app import BellboyCLIError
from pyknic.lib.fastapi.models.lobby import LobbyStrFeedbackResult, LobbyKeyValueFeedbackResult, LobbyCommandResult
from pyknic.lib.fastapi.models.lobby import LobbyListValueFeedbackResult
from pyknic.lib.fastapi.models.base import NullableModel


class BellboyConsole:
    """ Wraps and unify style and CLI behavior"""

    def __init__(self) -> None:
        """ Create a new console renderer
        """

        self.__console = rich.console.Console()
        self.__last_prompt: typing.Optional[str] = None

    def ask(self, question: str | None = None, password: bool = False) -> str:
        """ Ask a user for an input

        :param question: if defined then this question will be printed before prompt
        :param password: whether prompt should echo an input or not
        """
        if question:
            self.__console.print(rich.text.Text(question))
        result = rich.prompt.Prompt.ask(password=password)
        self.__last_prompt = result.strip()
        return self.__last_prompt

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

    def null_feedback(self, feedback: NullableModel) -> None:
        """Process null result.

        :param feedback: None as is =)
        """
        self.__console.print(rich.text.Text('<command succeeded without feedback>'))

    def list_feedback(self, feedback: LobbyListValueFeedbackResult) -> None:
        """Process null result.

        :param feedback: None as is =)
        """
        self.__console.print(rich.text.Text('Values received:'))
        for i in feedback.list_result:
            self.__console.print(rich.padding.Padding.indent(i, 4))

    def process_result(
        self,
        command_result: LobbyCommandResult
    ) -> None:
        """Print a result in a stylish way

        :param command_result: command result to print
        """
        if isinstance(command_result, LobbyStrFeedbackResult):
            self.str_feedback(command_result)
        elif isinstance(command_result, LobbyKeyValueFeedbackResult):
            self.kv_feedback(command_result)
        elif isinstance(command_result, LobbyListValueFeedbackResult):
            self.list_feedback(command_result)
        elif isinstance(command_result, NullableModel):
            self.null_feedback(command_result)
        else:
            raise BellboyCLIError('Unknown command result spotted! Check logs')
