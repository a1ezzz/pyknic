# -*- coding: utf-8 -*-
# pyknic/lib/integrated_commands/copier.py
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

# TODO: write docs
# TODO: write tests for the code
# TODO: make the remote LobbyCommandHandler command for copy
# TODO: make it possible to copy when destination is a directory

import typing

import pydantic

from pyknic.lib.capability import iscapable
from pyknic.lib.io.aio_wrapper import IOThrottler
from pyknic.lib.bellboy.app import BellBoyCommandHandler, register_bellboy_command
from pyknic.lib.fastapi.models.lobby import LobbyCommandResult, LobbyStrFeedbackResult
from pyknic.lib.io.aio_wrapper import AsyncWrapper
from pyknic.lib.io.clients import IOVirtualClient, IOClientProto
from pyknic.lib.uri import URI


class CopierCommandModel(pydantic.BaseModel):
    """ These settings define main backup options
    """

    source: str = pydantic.Field(description='source file to copy')

    destination: str = pydantic.Field(description='file destination')

    throttling: typing.Optional[int] = pydantic.Field(
        default=None, description='target data-rate (bytes per second) for file copying'
    )


@register_bellboy_command()
class BellBoyCopyCommand(BellBoyCommandHandler):
    """ This command backs up data
    """

    @classmethod
    def command_name(cls) -> str:
        """ The :meth:`.BellBoyCommandHandler.command_name` method implementation
        """
        return "copier"

    @classmethod
    def command_model(cls) -> typing.Type[pydantic.BaseModel]:
        """ The :meth:`.BellBoyCommandHandler.command_model` method implementation
        """
        return CopierCommandModel

    def __client_by_uri(self, uri_str: str) -> typing.Tuple[IOVirtualClient, URI, str]:
        original_uri = URI.parse(uri_str)
        file_name, client = IOVirtualClient.create_client_w_file_path(original_uri)
        return client, original_uri, file_name

    def __copy(self) -> LobbyCommandResult:
        assert (isinstance(self._args, CopierCommandModel))

        source_client, source_uri, source_file = self.__client_by_uri(self._args.source)
        destination_client, destination_uri, destination_file = self.__client_by_uri(
            self._args.destination
        )

        if not iscapable(source_client, IOClientProto.file_size):
            raise ValueError(f'The "{source_uri.scheme}" protocol implementation does not support file size checking')

        if not iscapable(source_client, IOClientProto.receive_file):
            raise ValueError(f'The "{source_uri.scheme}" protocol implementation does not file fetching')

        if not iscapable(destination_client, IOClientProto.upload_file):
            raise ValueError(f'The "{destination_uri.scheme}" protocol implementation does not file uploading')

        with source_client.open():
            with destination_client.open():

                read_generator = source_client.receive_file(source_file)
                sync_throttler = IOThrottler.sync_resender(read_generator, throttling=self._args.throttling)
                destination_client.upload_file(destination_file, sync_throttler)

                return LobbyStrFeedbackResult(
                    str_result=f'File from the {self._args.source} copied successfully to the {self._args.destination}'
                )

    async def exec(self) -> LobbyCommandResult:
        """ The :meth:`.BellBoyCommandHandler.exec` method implementation
        """
        caller = await AsyncWrapper.create(self.__copy)
        return await caller()  # type: ignore[no-any-return]
