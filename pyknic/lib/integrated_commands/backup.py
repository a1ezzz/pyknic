# -*- coding: utf-8 -*-
# pyknic/lib/fastapi/lobby_commands/backup.py
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

# TODO: write tests for the code
# TODO: make the remote LobbyCommandHandler command for backup, restore and validate

import base64
import shlex
import subprocess
import typing

import pydantic
import pydantic_settings

from pyknic.lib.io import IOGenerator
from pyknic.lib.io.aio_wrapper import IOThrottler, cag
from pyknic.lib.backup.archive_v1 import HashMethod, CompressionMode, BackupArchiveV1
from pyknic.lib.bellboy.app import BellBoyCommandHandler, register_bellboy_command
from pyknic.lib.fastapi.models.lobby import LobbyCommandResult, LobbyKeyValueFeedbackResult, LobbyStrFeedbackResult


class BackupSource(pydantic_settings.CliMutuallyExclusiveGroup):
    """ These settings define which data should be backed up
    """

    command: typing.Optional[str] = pydantic.Field(
        default=None,
        description='a command to execute, which stdout will be backed up'
    )
    files: typing.Optional[typing.List[str]] = pydantic.Field(
        default=None,
        description='a static files/directories list to backup'
    )
    files_command: typing.Optional[str] = pydantic.Field(
        validation_alias=pydantic.AliasChoices('files-command'),
        default=None,
        description='a command to execute and every line of the stdout will be treated as a file to backup'
    )


class BackupCommandModel(pydantic.BaseModel):
    """ These settings define main backup options
    """

    hash_algorithms: typing.Optional[typing.List[HashMethod]] = pydantic.Field(
        validation_alias=pydantic.AliasChoices('hash-algorithms'),
        default=None,
        description='list of hash algorithms to use'
    )

    throttling: typing.Optional[int] = pydantic.Field(
        default=None,
        description='target data-rate (bytes per second) for saving archive'
    )

    compression: typing.Optional[CompressionMode] = pydantic.Field(
        default=None,
        description='type of compression to use'
    )

    cipher_name: typing.Optional[str] = pydantic.Field(
        validation_alias=pydantic.AliasChoices('cipher-name'),
        default=None,
        description='cipher to use (will be enabled only if the encryption-key was set), '
        'like: AES-256-CBC (which is the default)'
    )

    encryption_key: typing.Optional[str] = pydantic.Field(
        validation_alias=pydantic.AliasChoices('encryption-key'),
        default=None,
        description='enable encryption and use the key for that'
    )

    extra_meta: typing.Optional[typing.Dict[str, typing.Any]] = pydantic.Field(
        validation_alias=pydantic.AliasChoices('extra-meta'),
        default=None,
        description='some extra data to include to the archive'
    )

    archive: str = pydantic.Field(
        description='a target path to archive file'
    )

    backup_source: BackupSource = pydantic.Field(
        validation_alias=pydantic.AliasChoices('backup-source'),
        description='defines what we will backup'
    )


@register_bellboy_command()
class BellBoyBackupCommand(BellBoyCommandHandler):
    """ This command backs up data
    """

    @classmethod
    def command_name(cls) -> str:
        """ The :meth:`.BellBoyCommandHandler.command_name` method implementation
        """
        return "backup"

    @classmethod
    def command_model(cls) -> typing.Type[pydantic.BaseModel]:
        """ The :meth:`.BellBoyCommandHandler.command_model` method implementation
        """
        return BackupCommandModel

    def __read_command(self, command_str: str) -> IOGenerator:
        """ Start a command and return stdout

        :param str command_str: the command to start
        """
        with subprocess.Popen(shlex.split(command_str), stdout=subprocess.PIPE) as pipe:
            assert(pipe.stdout is not None)
            yield from IOThrottler.sync_reader(pipe.stdout)

    def __read_files_by_command(self, command_str: str) -> typing.Generator[str, None, None]:
        """ Start a command and yield file names to backup

        :param command_str: the command to start
        """
        with subprocess.Popen(shlex.split(command_str), stdout=subprocess.PIPE) as pipe:
            assert(pipe.stdout is not None)
            next_line = pipe.stdout.readline()
            while next_line != b'':
                yield next_line.decode().rstrip('\n')
                next_line = pipe.stdout.readline()

    async def exec(self) -> LobbyCommandResult:
        """ The :meth:`.BellBoyCommandHandler.exec` method implementation
        """
        assert(isinstance(self._args, BackupCommandModel))

        archiver = BackupArchiveV1(
            hash_algorithms=self._args.hash_algorithms,
            throttling=self._args.throttling,
            compression=self._args.compression,
            cipher_name=self._args.cipher_name,
            encryption_key=self._args.encryption_key,
            extra_meta=self._args.extra_meta
        )

        with open(self._args.archive, 'wb') as archive_file:
            if self._args.backup_source.command is not None:
                await archiver.backup_io(self.__read_command(self._args.backup_source.command), archive_file)
            elif self._args.backup_source.files is not None:
                await archiver.backup_files(self._args.backup_source.files, archive_file)
            elif self._args.backup_source.files_command is not None:
                await archiver.backup_files(
                    self.__read_files_by_command(self._args.backup_source.files_command), archive_file
                )
            else:
                raise ValueError('Unknown backup source spotted!')

        with open(self._args.archive, 'rb') as archive_file:
            header = archiver.extract_header_meta(archive_file)
            tail = archiver.extract_tail_meta(archive_file)

        return LobbyKeyValueFeedbackResult(kv_result={
            "archiver_version": header.version,
            "archive_type": header.type.value,
            "created": header.created,
            "compression": header.compression.value,
            "cipher": header.cipher,
            "write_rate": tail.write_rate,
            "duration": tail.duration,
            "hashes": {x.algorithm.value: base64.b64encode(x.digest) for x in tail.hashes},
            "extra": header.extra,
        })


class ArchiveValidateCommandModel(pydantic.BaseModel):
    """ These settings define archive validation options
    """

    throttling: typing.Optional[int] = pydantic.Field(
        default=None,
        description='target data-rate (bytes per second) for archive reading'
    )

    archive: str = pydantic.Field(
        description='a target path to archive file'
    )


@register_bellboy_command()
class BellBoyArchiveValidateCommand(BellBoyCommandHandler):
    """ This command validate archive data
    """

    @classmethod
    def command_name(cls) -> str:
        """ The :meth:`.BellBoyCommandHandler.command_name` method implementation
        """
        return "backup-validate"

    @classmethod
    def command_model(cls) -> typing.Type[pydantic.BaseModel]:
        """ The :meth:`.BellBoyCommandHandler.command_model` method implementation
        """
        return ArchiveValidateCommandModel

    async def exec(self) -> LobbyCommandResult:
        """ The :meth:`.BellBoyCommandHandler.exec` method implementation
        """
        assert(isinstance(self._args, ArchiveValidateCommandModel))

        with open(self._args.archive, 'rb') as archive_file:
            await BackupArchiveV1.validate_archive(archive_file, throttling=self._args.throttling)

        return LobbyStrFeedbackResult(str_result=f'The "{self._args.archive}" archive is consistent!')


class RestoreCommandModel(pydantic.BaseModel):
    """ These settings define unarchiving options
    """

    validate_hashes: pydantic_settings.CliImplicitFlag[bool] = pydantic.Field(
        validation_alias=pydantic.AliasChoices('validate-hashes'),
        default=False,
        description='Whether to check hashes during restore or not'
    )

    throttling: typing.Optional[int] = pydantic.Field(
        default=None,
        description='target data-rate (bytes per second) for archive restoring'
    )

    encryption_key: typing.Optional[str] = pydantic.Field(
        validation_alias=pydantic.AliasChoices('encryption-key'),
        default=None,
        description='enable encryption and use the key for that'
    )

    archive: str = pydantic.Field(
        description='a target path to archive file'
    )

    restore_location: str = pydantic.Field(
        validation_alias=pydantic.AliasChoices('restore-location'),
        description='a target path to archive file'
    )


@register_bellboy_command()
class BellBoyRestoreCommand(BellBoyCommandHandler):
    """ These settings define unarchive options
    """

    @classmethod
    def command_name(cls) -> str:
        """ The :meth:`.BellBoyCommandHandler.command_name` method implementation
        """
        return "backup-restore"

    @classmethod
    def command_model(cls) -> typing.Type[pydantic.BaseModel]:
        """ The :meth:`.BellBoyCommandHandler.command_model` method implementation
        """
        return RestoreCommandModel

    async def exec(self) -> LobbyCommandResult:
        """ The :meth:`.BellBoyCommandHandler.exec` method implementation
        """
        assert(isinstance(self._args, RestoreCommandModel))

        archive = self._args.archive
        restore_location = self._args.restore_location

        with open(restore_location, 'wb') as restore_file:
            with open(archive, 'rb') as archive_file:
                unarchiver = BackupArchiveV1.extract_data(
                    archive_file, self._args.encryption_key, validate_hashes=self._args.validate_hashes
                )
                await cag(IOThrottler.async_writer(unarchiver, restore_file, throttling=self._args.throttling))

        return LobbyStrFeedbackResult(
            str_result=f'The "{archive}" archive has been restored to the "{restore_location}" file'
        )
