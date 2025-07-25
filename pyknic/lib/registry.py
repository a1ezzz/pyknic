# -*- coding: utf-8 -*-
# pyknic/lib/registry.py
#
# Copyright (C) 2019-2024 the pyknic authors and contributors
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

import hashlib
import typing

from abc import ABCMeta, abstractmethod

from pyknic.lib.verify import verify_value


class NoSuchAPIIdError(Exception):
    """ This exception is raised when a looked up API id is not found
    """
    pass


class DuplicateAPIIdError(Exception):
    """ This exception is raised when an attempt to register a descriptor with an id, that has been already
    registered, is made
    """
    pass


class APIRegistryProto(metaclass=ABCMeta):
    """ This is prototype for a general registry, object that stores anything by id. It may look like a dict object,
    but this class should be used in order to distinguish registry operation and commonly used dict
   """

    @abstractmethod
    def register(self, api_id: typing.Hashable, api_descriptor: typing.Any) -> None:
        """ Save the specified descriptor by the specified id

        :param api_id: unique id by which a descriptor may be found
        :param api_descriptor: descriptor that should be stored in this registry

        :raise DuplicateAPIIdError: when the specified API id has been registered already
        """
        raise NotImplementedError('This method is abstract')

    @abstractmethod
    def unregister(self, api_id: typing.Hashable) -> None:
        """ Remove the specified descriptor from registry

        :param api_id: id that will be removed from this registry

        :raise NoSuchAPIIdError: when the specified API id has not been registered
        """
        raise NotImplementedError('This method is abstract')

    @abstractmethod
    def get(self, api_id: typing.Hashable) -> typing.Any:
        """ Retrieve previously saved descriptor by an id

        :param api_id: id of a target descriptor

        :raise NoSuchAPIIdError: when the specified API id has not been registered
        """
        raise NotImplementedError('This method is abstract')

    @abstractmethod
    def has(self, api_id: typing.Hashable) -> bool:
        """ Check if this registry has the specified id

        :param api_id: id to check
        """
        raise NotImplementedError('This method is abstract')

    @abstractmethod
    def ids(self) -> typing.Generator[typing.Hashable, None, None]:
        """ Return generator that will return all ids that this registry have
        """
        raise NotImplementedError('This method is abstract')

    @abstractmethod
    def __iter__(self) -> typing.Generator[typing.Tuple[typing.Hashable, typing.Any], None, None]:
        """ Iterate over all the registered descriptors
        """
        raise NotImplementedError('This method is abstract')


class APIRegistry(APIRegistryProto):
    """ This is a basic registry implementation. It behaves like a dict mostly
    """

    def __init__(self, fallback_registry: typing.Optional[APIRegistryProto] = None):
        """ Create new registry

        :param fallback_registry: a registry where entries will be looked up if they are not found in
        this registry. This parameter helps to use all the items that are registered in other registry
        without registrations repeat
        """
        APIRegistryProto.__init__(self)
        self.__descriptors: typing.Dict[typing.Hashable, typing.Any] = dict()
        self.__fallback_registry = fallback_registry

    def register(self, api_id: typing.Hashable, api_descriptor: typing.Any) -> None:
        """ :meth:`.APIRegistryProto.register` method implementation
        """
        if api_id in self.__descriptors:
            raise DuplicateAPIIdError('The specified id "%s" has been used already' % str(api_id))
        self.__descriptors[api_id] = api_descriptor

    def unregister(self, api_id: typing.Hashable) -> None:
        """ :meth:`.APIRegistryProto.unregister` method implementation
        """
        if api_id not in self.__descriptors:
            raise NoSuchAPIIdError('No such entry: %s' % api_id)
        del self.__descriptors[api_id]

    def get(self, api_id: typing.Hashable) -> typing.Any:
        """ :meth:`.APIRegistryProto.register` method implementation
        """
        try:
            return self.__descriptors[api_id]
        except KeyError:
            pass

        if self.__fallback_registry is not None:
            return self.__fallback_registry.get(api_id)

        raise NoSuchAPIIdError('No such entry: %s' % api_id)

    def __getitem__(self, item: typing.Hashable) -> typing.Any:
        """ Shortcut to :meth:`.APIRegistryProto.get`
        """
        return self.get(item)

    def ids(self) -> typing.Generator[typing.Hashable, None, None]:
        """ :meth:`.APIRegistryProto.ids` method implementation
        """
        return (x for x in self.__descriptors.keys())

    def has(self, api_id: typing.Hashable) -> bool:
        """ :meth:`.APIRegistryProto.has` method implementation
        """
        return api_id in self.__descriptors

    def __contains__(self, item: typing.Hashable) -> bool:
        """ Shortcut to :meth:`.APIRegistryProto.has`
        """
        return self.has(item)

    def __iter__(self) -> typing.Generator[typing.Tuple[typing.Hashable, typing.Any], None, None]:
        """ :meth:`.APIRegistryProto.__iter__` method implementation
        """
        yield from self.__descriptors.items()


def register_api(
    registry: APIRegistryProto, api_id: typing.Optional[typing.Hashable] = None, callable_api_id: bool = False
) -> typing.Callable[..., typing.Callable[..., typing.Any]]:
    """ This decorator helps to register function, static method or class in the specified registry

    :param registry: registry to which a function should be registered
    :param api_id: id with which function will be registered. If it is not specified then function qualification \
    name will be used
    :param callable_api_id: whether 'api_id' is not an entry identifier but a callable (function) that accepts
    decorated object in order to retrieve a real id

    :raise ValueError: if the 'callable_api_id' variable is True but the 'api_id' is not callable object
    """
    def decorator_fn(decorated_obj: typing.Callable[..., typing.Any]) -> typing.Callable[..., typing.Any]:
        nonlocal api_id, callable_api_id  # noqa: F824
        if callable_api_id is True:
            if not callable(api_id):
                raise ValueError('Unable to retrieve an id - "api_id" is non-callable')
            api_id = api_id(decorated_obj)
        elif api_id is None:
            api_id = decorated_obj.__qualname__

        reg_id = api_id
        registry.register(reg_id, decorated_obj)
        return decorated_obj

    return decorator_fn


@verify_value(first_token=lambda x: x.isascii(), other_tokens=lambda x: x.isascii())
def hash_id_by_tokens(first_token: str, *other_tokens: str, pre_sort: bool = False) -> typing.Hashable:
    """Generate a determinate value as api_id by input tokens

    :param first_token: minimal required token to generate a hash
    :param other_tokens: other tokens for hash generation
    :param pre_sort: whether to sort tokens before hashing or not. Different parameters order will lead to different
    results when this value is False
    """

    tokens = [first_token, *other_tokens]

    if pre_sort:
        tokens.sort()

    result = hashlib.sha256()
    for i in tokens:
        result.update(i.encode('ascii'))
    return result.digest()
