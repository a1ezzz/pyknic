# -*- coding: utf-8 -*-
# pyknic/lib/bellboy/app.py
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

# TODO: document the code
# TODO: write tests for the code

import json
import logging
import typing

import aiohttp
import pydantic

from pyknic.lib.fastapi.lobby_fingerprint import LobbyFingerprint
from pyknic.path import root_path
from pyknic.lib.config import Config
from pyknic.lib.log import Logger
from pyknic.lib.verify import verify_value
from pyknic.lib.fastapi.models.lobby import LobbyCommandResult, LobbyStrFeedbackResult, LobbyKeyValueFeedbackResult
from pyknic.lib.fastapi.models.base import NullableResponseModel
from pyknic.lib.bellboy.console import BellboyConsole, BellboyPromptParser
from pyknic.lib.bellboy.error import BellboyCLIError
from pyknic.lib.bellboy.client import LobbyClient


class BellboyCLIApp:

    @verify_value(log_level=lambda x: x >= 0)
    def __init__(
        self,
        url: str,
        log_level: int = 0,
        config_file: typing.Optional[str] = None,
        token: typing.Optional[str] = None,
    ) -> None:

        self.__token_set = True if token else False
        self.__client = LobbyClient(url, token)
        self.__console = BellboyConsole()

        with open(root_path / 'lib/bellboy/config.yaml') as f:
            self.__config = Config(file_obj=f)

        if config_file is not None:
            with open(config_file) as f:
                self.__config.merge_file(f)

        self.__setup_logger(log_level)

    def __log_level(self, log_level: int) -> str:
        if log_level == 0:
            return "ERROR"
        elif log_level == 1:
            return "WARN"
        elif log_level == 2:
            return "INFO"
        else:
            return "DEBUG"

    def __setup_logger(self, log_level: int) -> None:
        formatter = logging.Formatter(
            str(self.__config['bellboy']['logger']['format_string']),
            str(self.__config['bellboy']['logger']['date_format'])
        )

        handler = logging.StreamHandler()
        handler.setFormatter(formatter)

        log_level = getattr(logging, self.__log_level(log_level))
        Logger.name = str(self.__config['bellboy']['logger']['app_name'])
        Logger.addHandler(handler)
        Logger.setLevel(log_level)

    async def start(self) -> None:
        Logger.info('Starting the "Bellboy" CLI Application')

        if not self.__token_set:
            try:
                # TODO: make token with config in order: args, configs, prompt
                token = self.__console.ask('Secret token was not set. Submit it now', password=True)
                self.__client.set_token(token)
            except (KeyboardInterrupt, EOFError):
                return

        async with aiohttp.ClientSession() as session:
            try:
                fingerprint = await self.__receive_fingerprint(session)
                contexts = await self.__receive_contexts(session, fingerprint)
                self.__console.log('')
            except BellboyCLIError as e:
                self.__console.critical(e)

            try:
                prompt_message: typing.Optional[str] = \
                    'Enter commands. Type "exit" or "quit" to finish this session. Type "help" for more information.'
                while await self.__client_session_one_shot(session, fingerprint, contexts, prompt_message):
                    prompt_message = None  # disable next messages
            except (KeyboardInterrupt, EOFError):
                pass

        self.__console.dump_history()

    async def __receive_fingerprint(self, session: aiohttp.ClientSession) -> LobbyFingerprint:
        self.__console.log(f'Connecting to a server with url {self.__client.url()}')
        fingerprint = await self.__client.fingerprint(session)
        self.__console.log(f'Received fingerprint: {str(fingerprint)}')
        return fingerprint

    async def __receive_contexts(
        self, session: aiohttp.ClientSession, fingerprint: LobbyFingerprint
    ) -> typing.Tuple[str]:

        self.__console.log('Checking contexts...')
        context_request = await self.__client.secure_request(
            fingerprint, session, 'get', '/contexts'
        )
        contexts = tuple(json.loads(context_request))
        self.__console.log(f'Number of received contexts: {len(contexts)}')
        return contexts

    async def __client_session_one_shot(
        self,
        session: aiohttp.ClientSession,
        fingerprint: LobbyFingerprint,
        contexts: typing.Tuple[str, ...],
        prompt_message: str | None
    ) -> bool:
        try:
            cli_input = self.__console.ask(prompt_message)

            if not cli_input:
                return True

            parser = BellboyPromptParser(cli_input, contexts)

            if parser.command().lower() in ('exit', 'quit'):
                self.__console.log('Quiting...')
                return False

            if parser.command().lower() == 'help':
                self.__console.log('Some day there will be some help')  # TODO: implement!
                return True

            command_result_txt = await self.__client.command_request(fingerprint, session, parser)
            # TODO: test command with extra args on the server side!

            command_result_json = json.loads(command_result_txt)
            command_result: LobbyCommandResult = \
                pydantic.TypeAdapter(LobbyCommandResult).validate_python(command_result_json, strict=True)

            if isinstance(command_result, LobbyStrFeedbackResult):
                self.__console.str_feedback(command_result)
            elif isinstance(command_result, LobbyKeyValueFeedbackResult):
                self.__console.kv_feedback(command_result)
            elif isinstance(command_result, NullableResponseModel):
                self.__console.null_feedback(command_result)
            else:
                raise BellboyCLIError('Unknown command result spotted! Check server logs')

        except BellboyCLIError as e:
            self.__console.error(str(e))
        else:
            self.__console.commit_history()

        return True
