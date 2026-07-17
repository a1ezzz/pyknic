# -*- coding: utf-8 -*-

import asyncio

import pytest

from pyknic.lib.uri import URI
from pyknic.lib.io.clients.proto import IOClientProto, DirectoryNotEmptyError, InvalidPartSize, NonSequentialPartNumbers
from pyknic.lib.io.clients.proto import PartsUploaderProto
from pyknic.lib.capability import iscapable

from fixtures.asyncio import pyknic_async_test


def test_exceptions() -> None:
    assert(issubclass(DirectoryNotEmptyError, Exception) is True)
    assert(issubclass(InvalidPartSize, Exception) is True)
    assert(issubclass(NonSequentialPartNumbers, Exception) is True)


@pyknic_async_test
async def test_abstract(module_event_loop: asyncio.AbstractEventLoop) -> None:

    pytest.raises(TypeError, PartsUploaderProto)
    pytest.raises(NotImplementedError, PartsUploaderProto.__enter__, None)  # type: ignore[call-overload]
    pytest.raises(
        NotImplementedError, PartsUploaderProto.__exit__, None, None, None, None
    )  # type: ignore[call-overload]
    pytest.raises(NotImplementedError, PartsUploaderProto.upload_part, None, b'b', 1)  # type: ignore[call-overload]

    pytest.raises(TypeError, IOClientProto)
    pytest.raises(NotImplementedError, IOClientProto.create_client, 'foo')  # type: ignore[call-overload]
    pytest.raises(NotImplementedError, IOClientProto.uri, None)  # type: ignore[call-overload]
    pytest.raises(NotImplementedError, IOClientProto.current_directory, None)  # type: ignore[call-overload]
    pytest.raises(NotImplementedError, IOClientProto.connect, None)  # type: ignore[call-overload]
    pytest.raises(NotImplementedError, IOClientProto.disconnect, None)  # type: ignore[call-overload]
    pytest.raises(
        NotImplementedError, IOClientProto.change_directory, None, '/path/to/dir'
    )  # type: ignore[call-overload]
    pytest.raises(NotImplementedError, IOClientProto.is_directory, None, 'dir_name')  # type: ignore[call-overload]
    pytest.raises(NotImplementedError, IOClientProto.list_directory, None)  # type: ignore[call-overload]
    pytest.raises(NotImplementedError, IOClientProto.make_directory, None, 'new_dir')  # type: ignore[call-overload]
    pytest.raises(NotImplementedError, IOClientProto.remove_directory, None, 'old_dir')  # type: ignore[call-overload]
    pytest.raises(
        NotImplementedError, IOClientProto.upload_file, None, 'file_name', [b'ggg']
    )  # type: ignore[call-overload]
    pytest.raises(
        NotImplementedError, IOClientProto.append_file, None, 'file_name', [b'ggg']
    )  # type: ignore[call-overload]
    pytest.raises(
        NotImplementedError, IOClientProto.update_file, None, 'file_name', [b'ggg']
    )  # type: ignore[call-overload]
    pytest.raises(NotImplementedError, IOClientProto.truncate_file, None, 'file_name', 1)  # type: ignore[call-overload]
    pytest.raises(NotImplementedError, IOClientProto.remove_file, None, 'file_name')  # type: ignore[call-overload]
    pytest.raises(NotImplementedError, IOClientProto.receive_file, None, 'remote_file')  # type: ignore[call-overload]
    pytest.raises(
        NotImplementedError, IOClientProto.receive_file_with_offset, None, 'remote_file', 10, 100
    )  # type: ignore[call-overload]
    pytest.raises(NotImplementedError, IOClientProto.file_size, None, 'remote_file')  # type: ignore[call-overload]
    pytest.raises(
        NotImplementedError, IOClientProto.upload_by_part, None, 'remote_file', 10
    )  # type: ignore[call-overload]

    class Client(IOClientProto):

        @classmethod
        def create_client(cls, uri: URI) -> 'Client':
            result = cls()
            result.obj_uri = uri  # type: ignore[attr-defined]  # it is just a test
            return result

        def uri(self) -> URI:
            return self.obj_uri  # type: ignore[attr-defined, no-any-return]  # it is just a test

    client = Client()
    assert(iscapable(client, IOClientProto.connect) is False)
    assert(iscapable(client, IOClientProto.disconnect) is False)
    assert(iscapable(client, IOClientProto.current_directory) is False)
    assert(iscapable(client, IOClientProto.change_directory) is False)
    assert(iscapable(client, IOClientProto.list_directory) is False)
    assert(iscapable(client, IOClientProto.make_directory) is False)
    assert(iscapable(client, IOClientProto.remove_directory) is False)
    assert(iscapable(client, IOClientProto.upload_file) is False)
    assert(iscapable(client, IOClientProto.remove_file) is False)
    assert(iscapable(client, IOClientProto.receive_file) is False)
    assert(iscapable(client, IOClientProto.file_size) is False)
