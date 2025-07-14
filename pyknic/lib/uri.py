# -*- coding: utf-8 -*-
# pyknic/lib/uri.py
#
# Copyright (C) 2017-2025 the pyknic authors and contributors
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
from urllib.parse import urlsplit, parse_qs, urlencode

from pyknic.lib.property import TypedDescriptor


URIQueryParameterType = typing.TypeVar('URIQueryParameterType')


class URIQueryInvalidSingleParameter(Exception):
    pass


class URI:
    """Class that represent URI as it is described in RFC 3986.

    https://datatracker.ietf.org/doc/html/rfc3986
    """

    scheme = TypedDescriptor(str)
    username = TypedDescriptor(str)
    password = TypedDescriptor(str)
    hostname = TypedDescriptor(str)
    port = TypedDescriptor(int, value_verifier=lambda x: x is None or (0 <= x <= 65535))
    path = TypedDescriptor(str)
    query = TypedDescriptor(str)
    fragment = TypedDescriptor(str)

    def __init__(
        self,
        scheme: typing.Optional[str] = None,
        username: typing.Optional[str] = None,
        password: typing.Optional[str] = None,
        hostname: typing.Optional[str] = None,
        port: typing.Optional[int] = None,
        path: typing.Optional[str] = None,
        query: typing.Optional[str] = None,
        fragment: typing.Optional[str] = None
    ):
        """Create a new URI."""
        self.scheme = scheme
        self.username = username
        self.password = password
        self.hostname = hostname
        self.port = port
        self.path = path.lstrip('/') if path else None
        self.query = query
        self.fragment = fragment

    def __str__(self) -> str:
        """ Return string that represents this URI."""
        # note the urlunsplit function in unpredictable because of this:
        #   >>> urlunsplit(('foo', '', '/path', None, None))
        #   'foo:/path'
        #   >>> urlunsplit(('http', '', '/path', None, None))
        #   'http:///path'

        def default_fn(value: typing.Optional[str], default_value: str) -> str:
            return value if value is not None else default_value

        def prefixed_value(value: typing.Optional[str], prefix: str, default_value: str) -> str:
            return prefix + value if value else default_value

        auth = default_fn(self.username, "")
        if auth and self.password:
            auth += ':' + self.password
        if auth:
            auth += '@'

        scheme = default_fn(self.scheme, "")
        if scheme:
            scheme += '://'

        netloc = default_fn(self.hostname, "")
        if netloc and self.port:
            netloc += ':' + str(self.port)

        path = prefixed_value(self.path, "/", "")
        query = prefixed_value(self.query, "?", "")
        fragment = prefixed_value(self.fragment, "#", "")

        return f'{scheme}{auth}{netloc}{path}{query}{fragment}'

    @classmethod
    def parse(cls, uri: str) -> 'URI':
        """Parse a string and return a new URI."""
        uri_components = urlsplit(uri)

        def adapter_str_fn(value: typing.Optional[str]) -> typing.Optional[str]:
            if value is not None and len(value) > 0:
                return value
            return None

        return cls(
            scheme=adapter_str_fn(uri_components.scheme),
            username=adapter_str_fn(uri_components.username),
            password=adapter_str_fn(uri_components.password),
            hostname=adapter_str_fn(uri_components.hostname),
            port=uri_components.port,
            path=adapter_str_fn(uri_components.path),
            query=adapter_str_fn(uri_components.query),
            fragment=adapter_str_fn(uri_components.fragment),
        )


class URIQuery:
    """ Represent a query component of URI. Any parameter may be present more than one time
    """
    # TODO: add quote/ unqoute to replace %XX

    def __init__(self) -> None:
        """ Create new query component
        """
        self.__query: typing.Dict[str, typing.List[str]] = dict()

    def update(self, name: str, value: typing.Union[str, typing.Tuple[str, ...]], append: bool = False) -> None:
        """Add/append/replace parameter in this query.

        :param name: parameter name to change
        :param value: parameter value to set, tuple for multiple values
        :param append: whether to append or replace parameter
        """
        value_list = list(value) if isinstance(value, tuple) else [value]
        if append and name in self.__query:
            value_list = self.__query[name] + value_list

        self.__query[name] = value_list

    def remove(self, name: str) -> None:
        """ Remove the specified parameter from this query.

        :param name: name of a parameter to remove
        """
        if name in self.__query:
            self.__query.pop(name)

    def __contains__(self, item: str) -> bool:
        """ Check if this query has the specified parameter

        :param item: parameter name to check
        """
        return item in self.__query

    def __str__(self) -> str:
        """ Encode parameters from this query, so it can be use in URI
        """
        parameters_keys = list(self.__query.keys())
        parameters_keys.sort()

        return '&'.join((urlencode({x: self.__query[x]}, True)) for x in parameters_keys)

    def __getitem__(self, item: str) -> typing.Tuple[str, ...]:
        """ Return all values for a signle parameter

        :param item: parameter name to retrieve
        """
        return tuple(self.__query[item])

    def __iter__(self) -> typing.Generator[str, None, None]:
        """ Iterate over parameters names
        """
        parameters_keys = list(self.__query.keys())
        parameters_keys.sort()
        yield from parameters_keys

    def parameters(self) -> typing.Generator[typing.Tuple[str, typing.Tuple[str, ...]], None, None]:
        """ Iterate over items, a pair of component name and component value will be raised
        """
        yield from ((x, tuple(y)) for x, y in self.__query.items())

    def single_parameter(
        self, name: str, type_adapter: typing.Callable[[str], URIQueryParameterType]
    ) -> URIQueryParameterType:
        """Return casted value of a single parameter of this query.

        :param name: parameter name to retrieve
        :param type_adapter: function to convert strings to a type (for example -- int, float and so on)
        """
        if name not in self:
            raise URIQueryInvalidSingleParameter(f'The {name} parameter is not defined')

        str_multiple_parameters = self[name]
        if len(str_multiple_parameters) != 1:
            raise URIQueryInvalidSingleParameter(f'The {name} parameter is set multiple times')

        str_parameter = str_multiple_parameters[0]
        if str_parameter == '':
            raise URIQueryInvalidSingleParameter(f'The {name} parameter has null value')

        return type_adapter(str_parameter)

    @classmethod
    def parse(cls, query_str: str) -> 'URIQuery':
        """ Parse string that represent query component from URI

        :param query_str: string without '?'-sign
        :type query_str: str
        """
        result = cls()

        if not query_str:
            return result

        parsed_query = parse_qs(query_str, keep_blank_values=True, strict_parsing=True)
        for name, value in parsed_query.items():
            result.update(name, tuple(value))

        return result
