# -*- coding: utf-8 -*-
# pyknic/lib/property.py
#
# Copyright (C) 2025 the pyknic authors and contributors
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


DescriptorType = typing.TypeVar('DescriptorType')


class TypedDescriptor(typing.Generic[DescriptorType]):
    """This is a @property-a-like class that helps to restrict variable type and possible stored values."""

    def __init__(
        self,
        t: typing.Type[DescriptorType],
        default_value: typing.Optional[DescriptorType] = None,
        value_verifier: typing.Optional[typing.Callable[[typing.Optional[DescriptorType]], bool]] = None
    ) -> None:
        """Create a new descriptor -- https://docs.python.org/3/howto/descriptor.html

        :param t: attribute type
        :param default_value: attribute initial value (None will be used by default)
        :param value_verifier: function that checks attribute values (must return True on valid values
        and False otherwise)
        """
        self.__type = t
        self.__name: typing.Optional[str] = None
        self.__default_value: typing.Optional[DescriptorType] = default_value
        self.__value_verifier = value_verifier

        if self.__default_value is not None:
            self.__check_var(self.__default_value)

    def __check_var(self, value: typing.Optional[DescriptorType]) -> None:
        """Check value and raise exception if it is not valid.

        :param value: value to check
        """
        if value is not None and not isinstance(value, self.__type):
            raise TypeError(f"Value's type is invalid. It must be of type {self.__type.__class__.__name__}")

        if self.__value_verifier and not self.__value_verifier(value):
            raise ValueError('Value does not match specified verifier')

    def __get__(
        self, instance: typing.Any, owner: typing.Optional[typing.Any] = None
    ) -> typing.Optional[DescriptorType]:
        """Return attribute value."""
        if not self.__name:
            raise TypeError('Attribute name was not set')
        return typing.cast(DescriptorType, instance.__dict__.get(self.__name, self.__default_value))

    def __set__(self, instance: typing.Any, value: typing.Optional[DescriptorType]) -> typing.Any:
        """Set attribute value."""
        if not self.__name:
            raise TypeError('Attribute name was not set')
        self.__check_var(value)
        instance.__dict__[self.__name] = value

    def __set_name__(self, owner: typing.Any, name: str) -> None:
        """Receive attribute name

        https://docs.python.org/3/reference/datamodel.html#object.__set_name__
        """
        self.__name = name
