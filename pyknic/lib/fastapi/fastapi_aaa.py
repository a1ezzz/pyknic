# -*- coding: utf-8 -*-
# pyknic/lib/fastapi/fastapi_aaa.py
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

import dataclasses
import secrets
import typing

from abc import ABCMeta, abstractmethod

import fastapi
import fastapi.security
import fastapi.security.http

from pyknic.lib.config import Config
from pyknic.lib.crypto.htpasswd import HTPasswd
from pyknic.lib.registry import APIRegistry, register_api


__default_fastapi_aaa_registry__ = APIRegistry()


@dataclasses.dataclass
class FastAPIIdentity:
    """ This dataclass defines a set of properties that are a result of successful authentication handler
    (ie :class:`.AuthenticationProviderProto`)
    """

    provider: str                                                     # handler's id that granted this identity
    identity: typing.Union[str, int]                                  # authorized user

    groups: typing.List[typing.Union[str, int]] = dataclasses.field(  # group names/ids this identity has
        default_factory=list
    )

    full_name: typing.Optional[str] = None                            # user's full name (if any)
    email: typing.Optional[str] = None                                # user's email address (if any)


class AuthenticationProviderProto(metaclass=ABCMeta):
    """ This prototype helps to authenticate users
    """

    @abstractmethod
    async def authenticate(self, request: fastapi.Request) -> typing.Optional[FastAPIIdentity]:
        """ Try to authenticate a request

        :param request: client request
        """
        raise NotImplementedError('This method is abstract')

    @abstractmethod
    def fastapi_handler(self) -> typing.Optional[typing.Type[fastapi.security.http.HTTPBase]]:
        """ FastAPI handler that is required for this provider to work
        """
        raise NotImplementedError('This method is abstract')

    @classmethod
    @abstractmethod
    def create(cls, provider_name: str, config: Config) -> 'AuthenticationProviderProto':
        """ Create this provider from config

        :param provider_name: unique provider name
        :param config: provider settings
        """
        raise NotImplementedError('This method is abstract')


@register_api(__default_fastapi_aaa_registry__, 'trust')
class TrustProvider(AuthenticationProviderProto):
    """ This provider casts every request as a request from a specific user
    """

    def __init__(self, provider_name: str, config: Config):
        """ Create a provider

        :param provider_name: unique provider name
        :param config: provider settings
        """
        self.__provider = provider_name
        self.__as_user = config['as_user'].as_str()

    def fastapi_handler(self) -> typing.Optional[typing.Type[fastapi.security.http.HTTPBase]]:
        """ :meth:`.AuthenticationProviderProto.fastapi_handler` implementation """
        return None

    async def authenticate(self, request: fastapi.Request) -> typing.Optional[FastAPIIdentity]:
        """ :meth:`.AuthenticationProviderProto.authenticate` implementation """
        return FastAPIIdentity(provider=self.__provider, identity=self.__as_user)

    @classmethod
    def create(cls, provider_name: str, config: Config) -> AuthenticationProviderProto:
        """ :meth:`.AuthenticationProviderProto.create` implementation """
        return cls(provider_name, config)


@register_api(__default_fastapi_aaa_registry__, 'bearer_static_token')
class BearerStaticTokenProvider(AuthenticationProviderProto):
    """ This provider casts a request as a request from a specific user if a bearer token matches
    """

    def __init__(self, provider_name: str, config: Config):
        """ Create a provider

        :param provider_name: unique provider name
        :param config: provider settings
        """
        self.__provider = provider_name
        self.__secret_token = config['secret_token'].as_str()
        self.__as_user = config['as_user'].as_str()

    def fastapi_handler(self) -> typing.Optional[typing.Type[fastapi.security.http.HTTPBase]]:
        """ :meth:`.AuthenticationProviderProto.fastapi_handler` implementation """
        return fastapi.security.HTTPBearer

    async def authenticate(self, request: fastapi.Request) -> typing.Optional[FastAPIIdentity]:
        """ :meth:`.AuthenticationProviderProto.authenticate` implementation """
        http_bearer = fastapi.security.HTTPBearer()
        http_creds = await http_bearer(request)

        if http_creds:
            encoded_bearer = http_creds.credentials

            if secrets.compare_digest(encoded_bearer, self.__secret_token):
                # note: compare_digest do comparison in a constant time
                return FastAPIIdentity(provider=self.__provider, identity=self.__as_user)

        return None

    @classmethod
    def create(cls, provider_name: str, config: Config) -> AuthenticationProviderProto:
        """ :meth:`.AuthenticationProviderProto.create` implementation """
        return cls(provider_name, config)


@register_api(__default_fastapi_aaa_registry__, 'htpasswd')
class HTPasswdProvider(AuthenticationProviderProto):
    """ This provider uses a htpasswd-file for authentication
    """

    def __init__(self, provider_name: str, config: Config):
        """ Create a provider

        :param provider_name: unique provider name
        :param config: provider settings
        """
        self.__provider = provider_name
        self.__file = config['file'].as_str()

        self.__htpasswd = HTPasswd.read_file(self.__file)

    def fastapi_handler(self) -> typing.Optional[typing.Type[fastapi.security.http.HTTPBase]]:
        """ :meth:`.AuthenticationProviderProto.fastapi_handler` implementation """
        return fastapi.security.HTTPBasic

    async def authenticate(self, request: fastapi.Request) -> typing.Optional[FastAPIIdentity]:
        """ :meth:`.AuthenticationProviderProto.authenticate` implementation """
        http_basic = fastapi.security.HTTPBasic()
        http_creds = await http_basic(request)

        if http_creds:
            if self.__htpasswd.match(http_creds.username, http_creds.password):
                return FastAPIIdentity(provider=self.__provider, identity=http_creds.username)

        return None

    @classmethod
    def create(cls, provider_name: str, config: Config) -> AuthenticationProviderProto:
        """ :meth:`.AuthenticationProviderProto.create` implementation """
        return cls(provider_name, config)
