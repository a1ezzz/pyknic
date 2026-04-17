
import os
import socket
import threading
import typing
import pathlib

import paramiko
import pytest

from pyknic.lib.tasks.proto import TaskProto
from pyknic.lib.tasks.thread_executor import ThreadExecutor
from pyknic.lib.thread import CriticalResource

from fixtures.common import log_exceptions


class SSHServer(paramiko.server.ServerInterface):
    """This server allows any connect.

    For details read the https://docs.paramiko.org/en/stable/api/server.html#paramiko.server.ServerInterface
    """

    def check_auth_password(self, username: str, password: str) -> int:
        return paramiko.common.AUTH_SUCCESSFUL

    def check_auth_publickey(self, username: str, key: paramiko.pkey.PKey) -> int:
        return paramiko.common.AUTH_SUCCESSFUL

    def check_channel_request(self, kind: str, chanid: int) -> int:
        return paramiko.common.OPEN_SUCCEEDED

    def check_channel_shell_request(self, channel: paramiko.Channel) -> bool:
        return True

    def check_channel_pty_request(
        self,
        channel: paramiko.Channel,
        term: bytes,
        width: int,
        height: int,
        pixelwidth: int,
        pixelheight: int,
        modes: bytes
    ) -> bool:
        return True


class SFTPFileHandler(paramiko.sftp_handle.SFTPHandle):
    """Represent a single file IO

    Details are here -- https://docs.paramiko.org/en/stable/api/sftp.html#paramiko.sftp_handle.SFTPHandle
    """

    @log_exceptions
    def __init__(self, real_path: pathlib.Path, flags: int, force_open: bool = True):
        paramiko.sftp_handle.SFTPHandle.__init__(self, flags)
        self.__real_path = real_path
        self.__flags = flags
        self.__file_int = 0

        if force_open:
            self.__force_open()

    def __force_open(self) -> None:
        if not self.__file_int:
            self.__file_int = os.open(self.__real_path, self.__flags)

    @log_exceptions
    def chattr(self, attr: paramiko.SFTPAttributes) -> int:
        # The only working option is a size changing

        if attr.st_uid is not None:
            raise NotImplementedError('To Be Implemented')

        if attr.st_gid is not None:
            raise NotImplementedError('To Be Implemented')

        if attr.st_mode is not None:
            raise NotImplementedError('To Be Implemented')

        if attr.st_atime is not None:
            raise NotImplementedError('To Be Implemented')

        if attr.st_mtime is not None:
            raise NotImplementedError('To Be Implemented')

        if attr.st_size is not None:
            os.truncate(self.__file_int, attr.st_size)

        return paramiko.sftp.SFTP_OK

    @log_exceptions
    def close(self) -> None:
        os.close(self.__file_int)
        self.__file_int = 0

    @log_exceptions
    def read(self, offset: int, length: int) -> bytes:
        self.__force_open()
        os.lseek(self.__file_int, offset, os.SEEK_SET)
        return os.read(self.__file_int, length)

    @log_exceptions
    def stat(self) -> paramiko.SFTPAttributes:
        attr = paramiko.SFTPAttributes.from_stat(self.__real_path.stat())
        attr.filename = self.__real_path.parts[-1]
        return attr

    @log_exceptions
    def write(self, offset: int, data: bytes) -> int:
        self.__force_open()
        os.lseek(self.__file_int, offset, os.SEEK_SET)
        os.write(self.__file_int, data)
        return paramiko.sftp.SFTP_OK


class SFTPHandler(paramiko.SFTPServerInterface):
    """Handles basic SFTP commands

    https://docs.paramiko.org/en/latest/api/sftp.html#paramiko.sftp_si.SFTPServerInterface
    """

    @log_exceptions
    def __init__(self, server_obj: SSHServer, base_directory: str, *args: typing.Any, **kwargs: typing.Any) -> None:
        paramiko.SFTPServerInterface.__init__(self, server_obj, *args, **kwargs)
        self.__base_directory = pathlib.Path(base_directory)

    def __real_path(self, path: str) -> pathlib.Path:
        canon_path = pathlib.Path(self.canonicalize(path)).relative_to('/')
        return self.__base_directory / canon_path

    @log_exceptions
    def list_folder(self, path: str) -> typing.Union[typing.List[paramiko.sftp_handle.SFTPHandle], int]:
        try:
            return [SFTPFileHandler(x, 0, force_open=False).stat() for x in self.__real_path(path).iterdir()]
        except OSError as e:
            return paramiko.SFTPServer.convert_errno(e.errno)  # type: ignore[arg-type]

    @log_exceptions
    def lstat(self, path: str) -> typing.Union[paramiko.sftp_handle.SFTPHandle, int]:
        handler = SFTPFileHandler(self.__real_path(path), 0, force_open=False)
        return handler.stat()  # type: ignore[no-any-return]

    @log_exceptions
    def stat(self, path: str) -> typing.Union[paramiko.sftp_handle.SFTPHandle, int]:
        handler = SFTPFileHandler(self.__real_path(path), 0, force_open=False)
        return handler.stat()  # type: ignore[no-any-return]

    @log_exceptions
    def mkdir(self, path: str, attr: paramiko.SFTPAttributes) -> int:
        try:
            self.__real_path(path).mkdir()
            return paramiko.sftp.SFTP_OK
        except OSError as e:
            return paramiko.SFTPServer.convert_errno(e.errno)  # type: ignore[arg-type]

    @log_exceptions
    def rmdir(self, path: str) -> int:
        self.__real_path(path).rmdir()
        return paramiko.sftp.SFTP_OK

    @log_exceptions
    def remove(self, path: str) -> int:
        self.__real_path(path).unlink()
        return paramiko.sftp.SFTP_OK

    @log_exceptions
    def open(self, path: str, flags: int, attr: paramiko.SFTPAttributes) -> paramiko.sftp_handle.SFTPHandle:
        return SFTPFileHandler(self.__real_path(path), flags)


class SFTPTransportTask(TaskProto, CriticalResource):
    """A task for a thread to work with raw sockets
    """

    @log_exceptions
    def __init__(
        self, received_socket: socket.socket, server: SSHServer, server_key: paramiko.RSAKey, base_dir: str
    ) -> None:
        TaskProto.__init__(self)
        CriticalResource.__init__(self)
        self.received_socket = received_socket
        self.server = server
        self.server_key = server_key
        self.base_dir = base_dir
        self.__transport: typing.Optional[paramiko.Transport] = None

    @log_exceptions
    def start(self) -> None:

        with self.critical_context():
            self.__transport = paramiko.Transport(self.received_socket)
            self.__transport.add_server_key(self.server_key)
            self.__transport.set_subsystem_handler(
                'sftp', paramiko.SFTPServer, SFTPHandler, self.base_dir
            )

            self.__transport.start_server(server=self.server)

            chan: typing.Optional[paramiko.channel.Channel] = self.__transport.accept()
            if not chan:
                raise RuntimeError("Failed to create SFTP channel")

        self.__transport.join()
        self.__transport = None

    @log_exceptions
    def stop(self) -> None:
        with self.critical_context():
            if self.__transport:
                self.__transport.close()


class SFTPServerTask(TaskProto, CriticalResource):
    """A task for a SFTP server
    """

    @log_exceptions
    def __init__(self, bind_port: int, base_dir: str, executor: ThreadExecutor):
        TaskProto.__init__(self)
        CriticalResource.__init__(self)

        self.bind_port = bind_port
        self.base_dir = base_dir
        self.executor = executor

        self.init_event = threading.Event()
        self.stop_request = threading.Event()
        self.client_connections: typing.List[SFTPTransportTask] = []

        self.raw_socket: typing.Optional[socket.socket] = None
        self.paramiko_server: typing.Optional[SSHServer] = None
        self.paramiko_server_key: typing.Optional[paramiko.RSAKey] = None

    @log_exceptions
    def start(self) -> None:
        self.raw_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.raw_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, True)
        self.raw_socket.bind(('127.0.0.1', self.bind_port))
        self.raw_socket.listen()

        self.paramiko_server = SSHServer()
        self.paramiko_server_key = paramiko.RSAKey.generate(bits=1024)

        self.init_event.set()

        try:
            connection, client_address = self.raw_socket.accept()

            while not self.stop_request.is_set():

                with self.critical_context():
                    new_transport = SFTPTransportTask(
                        connection, self.paramiko_server, self.paramiko_server_key, self.base_dir
                    )
                    self.executor.submit_task(new_transport)
                    self.client_connections.append(new_transport)

                connection, _ = self.raw_socket.accept()

        except OSError:  # skips raw_socket.accept termination
            pass

    @log_exceptions
    def stop(self) -> None:
        assert(self.raw_socket)

        self.stop_request.set()
        with self.critical_context():
            for t in self.client_connections:
                t.stop()
                self.executor.wait_task(t)
        self.client_connections.clear()

        self.raw_socket.shutdown(socket.SHUT_RDWR)


sftp_fixture: typing.TypeAlias = typing.Tuple[ThreadExecutor, SFTPServerTask]


@pytest.fixture
def sftp_server(request: pytest.FixtureRequest) -> typing.Generator[sftp_fixture, None, None]:

    ssh_port = request.param if hasattr(request, 'param') else 22

    executor = ThreadExecutor()
    sftp_task = SFTPServerTask(bind_port=ssh_port, base_dir='/tmp', executor=executor)
    executor.submit_task(sftp_task)
    sftp_task.init_event.wait()

    yield executor, sftp_task

    sftp_task.stop()
    executor.wait_task(sftp_task)
