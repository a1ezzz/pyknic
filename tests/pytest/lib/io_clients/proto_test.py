# -*- coding: utf-8 -*-

import asyncio
import pytest

from pyknic.lib.uri import URI
from pyknic.lib.io_clients.proto import ClientConnectionError, IOClientProto
from pyknic.lib.capability import iscapable

from fixtures.asyncio import pyknic_async_test


def test_exceptions() -> None:
    assert(issubclass(ClientConnectionError, Exception) is True)


@pyknic_async_test
async def test_abstract(module_event_loop: asyncio.AbstractEventLoop) -> None:
    pytest.raises(TypeError, IOClientProto)
    pytest.raises(NotImplementedError, IOClientProto.create_client, 'foo')
    pytest.raises(NotImplementedError, IOClientProto.uri, None)
    pytest.raises(NotImplementedError, IOClientProto.current_directory, None)

    with pytest.raises(NotImplementedError):
        await IOClientProto.connect(None)  # type: ignore[arg-type]  # it is just a test

    with pytest.raises(NotImplementedError):
        await IOClientProto.disconnect(None)  # type: ignore[arg-type]  # it is just a test

    with pytest.raises(NotImplementedError):
        await IOClientProto.change_directory(None, '/path/to/dir')  # type: ignore[arg-type]  # it is just a test

    with pytest.raises(NotImplementedError):
        await IOClientProto.list_directory(None)  # type: ignore[arg-type]  # it is just a test

    with pytest.raises(NotImplementedError):
        await IOClientProto.make_directory(None, 'new_dir')  # type: ignore[arg-type]  # it is just a test

    with pytest.raises(NotImplementedError):
        await IOClientProto.remove_directory(None, 'old_dir')  # type: ignore[arg-type]  # it is just a test

    with pytest.raises(NotImplementedError):
        await IOClientProto.upload_file(None, 'file_name', None)  # type: ignore[arg-type]  # it is just a test

    with pytest.raises(NotImplementedError):
        await IOClientProto.remove_file(None, 'file_name')  # type: ignore[arg-type]  # it is just a test

    with pytest.raises(NotImplementedError):
        await IOClientProto.receive_file(
            None, 'remote_file', 'local_file'  # type: ignore[arg-type]  # it is just a test
        )

    with pytest.raises(NotImplementedError):
        await IOClientProto.file_size(
            None, 'remote_file'  # type: ignore[arg-type]  # it is just a test
        )

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

    assert(client.directory_sep() == '/')
