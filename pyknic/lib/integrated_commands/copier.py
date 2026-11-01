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
# TODO: make the remote LobbyCommandHandler command for copy

import typing

import pydantic
import pydantic_settings

from pyknic.lib.capability import iscapable
from pyknic.lib.io.aio_wrapper import IOThrottler
from pyknic.lib.bellboy.app import BellBoyCommandHandler, register_bellboy_command
from pyknic.lib.fastapi.models.lobby import LobbyCommandResult, LobbyStrFeedbackResult
from pyknic.lib.io.aio_wrapper import AsyncWrapper
from pyknic.lib.io.clients import IOVirtualClient, IOClientProto, WalkEntryType
from pyknic.lib.uri import URI

from pyknic.lib.integrated_commands.commands_version import __plugin_version__


class CopierCommandModel(pydantic.BaseModel):
    """ These settings define main backup options
    """

    source: str = pydantic.Field(description='source file to copy')

    destination: str = pydantic.Field(description='file destination')

    throttling: typing.Optional[int] = pydantic.Field(
        default=None, description='target data-rate (bytes per second) for file copying'
    )

    recursive: pydantic_settings.CliImplicitFlag[bool] = pydantic.Field(
        default=False,
        description='recursively copy files and directories'
    )


@register_bellboy_command()
class BellBoyCopyCommand(BellBoyCommandHandler):
    """ This command backs up data
    """

    @classmethod
    def bellboy_command_description(cls) -> typing.Optional[str]:
        """ The :meth:`.BellBoyCommandHandler.bellboy_command_description` method implementation
        """
        return 'A general copying call. This call will be slower than general tools. And this command will be ' \
            'copy simlinks as files. But it may be useful since supports different protocols as is, so may copy ' \
            'files from SFTP to S3 without temporary files'

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
        fname, fixed_uri = original_uri.get_file()
        client = IOVirtualClient.create_client(fixed_uri)
        return client, original_uri, fname

    def __copy_file(
        self,
        source_client: IOVirtualClient,
        destination_client: IOVirtualClient,
        source_file: str,
        destination_file: str,
        throttling: typing.Optional[int] = None,
    ) -> None:
        read_generator = source_client.receive_file(source_file)
        sync_throttler = IOThrottler.sync_resender(read_generator, throttling=throttling)
        destination_client.upload_file(destination_file, sync_throttler)

    def __copy(self) -> LobbyCommandResult:
        if not isinstance(self._args, CopierCommandModel):
            raise TypeError('Invalid command arguments type')

        source_client, source_uri, source_file = self.__client_by_uri(self._args.source)
        destination_client, destination_uri, destination_file = self.__client_by_uri(
            self._args.destination
        )

        if not iscapable(source_client, IOClientProto.file_size, IOClientProto.receive_file):
            raise ValueError(
                f'The "{source_uri.scheme}" protocol implementation does not support one feature at least: '
                'file size checking, file fetching'
            )

        if not iscapable(destination_client, IOClientProto.upload_file):
            raise ValueError(f'The "{destination_uri.scheme}" protocol implementation does not file uploading')

        if self._args.recursive:
            if not iscapable(
                source_client,
                IOClientProto.is_directory,
                IOClientProto.list_directory,
                IOClientProto.change_directory
            ):
                raise ValueError(
                    f'The "{source_uri.scheme}" protocol implementation does not support one feature at least: '
                    'directory checking, directory listing, directory navigation'
                )

            if not iscapable(
                destination_client,
                IOClientProto.is_directory,
                IOClientProto.list_directory,
                IOClientProto.change_directory
            ):
                raise ValueError(
                    f'The "{destination_uri.scheme}" protocol implementation does not support one feature at least: '
                    'directory checking, directory listing, directory navigation'
                )

        with source_client.open() as source_context:
            with destination_client.open():

                is_source_dir = (
                    iscapable(source_client, IOClientProto.is_directory)
                    and source_client.is_directory(source_file)
                )

                if is_source_dir:

                    if not self._args.recursive:
                        raise IsADirectoryError('Copy request for a directory without a recursive flag')

                    source_client.change_directory(source_file)
                    destination_client.change_directory(destination_file)

                    start_src_dir = source_client.current_directory()
                    start_dest_dir = destination_client.current_directory()

                    for i in source_context.walk(relative_path=True):
                        if i.entry_type == WalkEntryType.directory:
                            destination_client.change_directory(start_dest_dir)
                            destination_client.change_directory(i.parent_directory)

                            if not destination_client.is_directory(i.entry_name):
                                destination_client.make_directory(i.entry_name)
                        elif i.entry_type == WalkEntryType.general_file:
                            source_client.change_directory(start_src_dir)
                            source_client.change_directory(i.parent_directory)

                            destination_client.change_directory(start_dest_dir)
                            destination_client.change_directory(i.parent_directory)

                            self.__copy_file(
                               source_client,
                               destination_client,
                               i.entry_name,
                               i.entry_name,
                               throttling=self._args.throttling
                            )
                        else:
                            raise RuntimeError(f'Uknown walk entry type -- {i.entry_type}')

                    return LobbyStrFeedbackResult(
                        str_result=(
                            f'Directory from the {self._args.source} copied successfully to the '
                            f'{self._args.destination}'
                        ),
                        plugin_version=__plugin_version__
                    )

                # not is_source_dir

                if (
                    iscapable(destination_client, IOClientProto.is_directory)
                    and destination_client.is_directory(destination_file)
                ):
                    destination_client.change_directory(destination_file)
                    destination_file = source_file

                    if (
                        iscapable(destination_client, IOClientProto.is_directory)
                        and destination_client.is_directory(destination_file)
                    ):
                        raise IsADirectoryError(f'Cannot overwrite directory "{destination_file}" with file')

                self.__copy_file(
                    source_client, destination_client, source_file, destination_file, throttling=self._args.throttling
                )

                return LobbyStrFeedbackResult(
                    str_result=f'File from the {self._args.source} copied successfully to the {self._args.destination}',
                    plugin_version=__plugin_version__
                )

    async def exec(self) -> LobbyCommandResult:
        """ The :meth:`.BellBoyCommandHandler.exec` method implementation
        """
        caller = await AsyncWrapper.create(self.__copy)
        return await caller()  # type: ignore[no-any-return]
