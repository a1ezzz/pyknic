
import asyncio
import base64
import io
import pathlib
import typing

import fastapi.datastructures
import fastapi.security
import pytest

from pyknic.lib.config import Config
from pyknic.lib.fastapi.fastapi_aaa import FastAPIIdentity, AuthenticationProviderProto, TrustProvider
from pyknic.lib.fastapi.fastapi_aaa import BearerStaticTokenProvider, HTPasswdProvider

from fixtures.asyncio import pyknic_async_test


@pyknic_async_test
async def test_abstract(module_event_loop: asyncio.AbstractEventLoop) -> None:
    pytest.raises(TypeError, AuthenticationProviderProto)

    with pytest.raises(NotImplementedError):
        await AuthenticationProviderProto.authenticate(None, None)  # type: ignore[arg-type]  # test only

    with pytest.raises(NotImplementedError):
        AuthenticationProviderProto.fastapi_handler(None)  # type: ignore[arg-type]  # test only

    with pytest.raises(NotImplementedError):
        AuthenticationProviderProto.create(None, None)  # type: ignore[arg-type]  # test only


class RequestMock:

    def __init__(self, headers: typing.Optional[typing.Dict[str, str]] = None):
        self.__headers = fastapi.datastructures.Headers(headers=headers)

    @property
    def headers(self) -> fastapi.datastructures.Headers:
        return self.__headers


class TestTrustProvider:

    __trust_yaml__ = """
    as_user: 'test-username'
    """

    @pyknic_async_test
    async def test(self, module_event_loop: asyncio.AbstractEventLoop) -> None:
        config = Config(file_obj=io.StringIO(self.__trust_yaml__))
        provider = TrustProvider.create('test-provider', config)
        assert(isinstance(provider, TrustProvider) is True)

        assert(provider.fastapi_handler() is None)

        identity = await provider.authenticate(RequestMock())  # type: ignore[arg-type]  # this is a mock
        assert(isinstance(identity, FastAPIIdentity))
        assert(identity.provider == 'test-provider')
        assert(identity.identity == 'test-username')
        assert(identity.groups == [])
        assert(identity.full_name is None)
        assert(identity.email is None)


class TestBearerStaticTokenProvider:

    __token_yaml__ = """
    secret_token: tkn
    as_user: 'test-username'
    """

    @pyknic_async_test
    async def test(self, module_event_loop: asyncio.AbstractEventLoop) -> None:
        config = Config(file_obj=io.StringIO(self.__token_yaml__))
        provider = BearerStaticTokenProvider.create('test-provider', config)
        assert(isinstance(provider, BearerStaticTokenProvider) is True)

        assert(provider.fastapi_handler() is fastapi.security.HTTPBearer)

        with pytest.raises(fastapi.exceptions.HTTPException):
            # no bearer header
            _ = await provider.authenticate(RequestMock())  # type: ignore[arg-type]  # this is a mock

        identity = await provider.authenticate(
            RequestMock({"Authorization": "Bearer tkn"})  # type: ignore[arg-type]  # this is a mock
        )

        assert(isinstance(identity, FastAPIIdentity))
        assert(identity.provider == 'test-provider')
        assert(identity.identity == 'test-username')
        assert(identity.groups == [])
        assert(identity.full_name is None)
        assert(identity.email is None)


class TestHTPasswdProvider:

    __htpasswd_yaml__ = """
    file: {}
    """

    @pyknic_async_test
    async def test(self, module_event_loop: asyncio.AbstractEventLoop, tmp_path: pathlib.Path) -> None:
        htpasswd_file = tmp_path / "htpasswd"

        with htpasswd_file.open('w') as f:
            f.write('foo:$2y$05$Z7/3diNsWaUZ1JtEqQRdu.78F86tPEzPn/nEBTSVVyIugQtkAyRVK\n')  # foo:bar

        config = Config(file_obj=io.StringIO(self.__htpasswd_yaml__.format(str(htpasswd_file))))
        provider = HTPasswdProvider.create('test-provider', config)
        assert(provider.fastapi_handler() is fastapi.security.HTTPBasic)

        with pytest.raises(fastapi.exceptions.HTTPException):
            # no bearer header
            _ = await provider.authenticate(RequestMock())  # type: ignore[arg-type]  # this is a mock

        identity = await provider.authenticate(
            RequestMock(  # type: ignore[arg-type]  # this is a mock
                {"Authorization": f"Basic {base64.b64encode(b'foo:bar').decode('ascii')}"}
            )
        )

        assert(isinstance(identity, FastAPIIdentity))
        assert(identity.provider == 'test-provider')
        assert(identity.identity == 'foo')
        assert(identity.groups == [])
        assert(identity.full_name is None)
        assert(identity.email is None)
