# -*- coding: utf-8 -*-
# pyknic/lib/config.py
#
# Copyright (C) 2024 the pyknic authors and contributors
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

import yaml

from pyknic.lib.verify import verify_type, verify_value


RawConfigPlainTypes: typing.TypeAlias = typing.Optional[typing.Union[int, float, str, bool]]

RawConfigComplexType: typing.TypeAlias = typing.Union[
    RawConfigPlainTypes,
    typing.List['RawConfigComplexType'],
    typing.Dict[str, typing.Union['RawConfigComplexType', '_ConfigImplementation']]
]


class _ConfigImplementation:
    """This is basic storage and basic app configuration implementation.

    It is private and helps to implement more complex logic.
    """

    def __init__(self, value: RawConfigComplexType | '_ConfigImplementation'):
        """Create a new configuration and initialize it with a value.

        :param value: initial value
        """

        @verify_type(init_value=(None, dict, list, int, float, str, bool, _ConfigImplementation))
        def init(init_value: RawConfigComplexType | '_ConfigImplementation') -> None:
            """Just decorated __init__ method that is called later."""
            self.__value: RawConfigComplexType = \
                init_value.__value if isinstance(init_value, _ConfigImplementation) else init_value

        init(value)

    def raw_type(self) -> typing.Optional[type]:
        """Return basic type of the inside stored object."""
        return type(self.__value) if self.__value is not None else None

    def __ensure_type(self, *value_types: type) -> None:
        """Check that inside storage suites specified types.

        :param value_types: types that storage should be suited
        """
        assert(len(value_types) >= 1)

        if not isinstance(self.__value, value_types):
            raise TypeError('Invalid type for config entry')

    def is_none(self) -> bool:
        """Return that this configuration holds nothing ie None."""
        return self.__value is None

    def is_dict(self) -> bool:
        """Return that inside storage is a dict object."""
        return isinstance(self.__value, dict)

    def __as_dict(self) -> typing.Dict[str, RawConfigComplexType | '_ConfigImplementation']:
        """Check that inside storage is a dict object. Also adapt code to mypy."""
        self.__ensure_type(dict)
        return typing.cast(typing.Dict[str, RawConfigComplexType | _ConfigImplementation], self.__value)

    def dict_iterate(self) -> typing.Generator[
        typing.Tuple[str, RawConfigComplexType | '_ConfigImplementation'],
        None,
        None
    ]:
        """Return generator that yields keys and values."""
        yield from self.__as_dict().items()

    def dict_properties(self) -> typing.Set[str]:
        """Return keys that this storage holds."""
        return set(self.__as_dict().keys())

    def dict_has(self, name: str) -> bool:
        """Return True if storage has the specified key.

        :param name: a key to check
        """
        return name in self.__as_dict().keys()

    def dict_property(self, name: str) -> '_ConfigImplementation':
        """Return a value that is stored within a key.

        :param name: a key which value should be retrieved
        """
        dict_obj = self.__as_dict()
        if name not in dict_obj:
            raise ValueError(f'There is no {name} property in a configuration object')
        return _ConfigImplementation(dict_obj[name])

    def dict_update(self, name: str, value: RawConfigComplexType | '_ConfigImplementation') -> None:
        """Insert or update a value that is stored within a key.

        :param name: a key which value should be updated
        :param value: new value
        """
        self.__as_dict()[name] = _ConfigImplementation(value).__value

    def dict_clear(self) -> None:
        """Empty internal storage from every key."""
        self.__as_dict().clear()

    def is_list(self) -> bool:
        """Return that inside storage is a list object."""
        return isinstance(self.__value, list)

    def __as_list(self) -> typing.List[RawConfigComplexType | '_ConfigImplementation']:
        """Check that inside storage is a list object. Also adapt code to mypy."""
        self.__ensure_type(list)
        return typing.cast(typing.List[RawConfigComplexType | _ConfigImplementation], self.__value)

    def list_iterate(self) -> typing.Generator['_ConfigImplementation', None, None]:
        """Return generator that yields values from internal list."""
        for i in self.__as_list():
            yield _ConfigImplementation(i)

    def list_get(self, item_index: int) -> '_ConfigImplementation':
        """Get item from internal list by an index.

        :param item_index: index of item to get
        """
        return _ConfigImplementation(self.__as_list()[item_index])

    def is_plain(self) -> bool:
        """Return True if inside storage holds a "plain" object like string or integer."""
        return isinstance(self.__value, (bool, int, float, str))

    def __bool__(self) -> bool:
        """Return value of the internal boolean storage."""
        self.__ensure_type(bool)
        return typing.cast(bool, self.__value)

    def __int__(self) -> int:
        """Return value of the internal integer storage."""
        self.__ensure_type(int)
        return typing.cast(int, self.__value)

    def __float__(self) -> float:
        """Return value of the internal floating-point number storage."""
        self.__ensure_type(float)
        return typing.cast(float, self.__value)

    def __str__(self) -> str:
        """Return value of the internal string storage."""
        self.__ensure_type(str)
        return typing.cast(str, self.__value)


class _ConfigStorage:
    """This is a shared storage, that is shared between target configuration classes."""

    def __init__(self) -> None:
        """Create a shared storage."""
        self._config = _ConfigImplementation(None)


class Config(_ConfigStorage):
    """Dict-a-like configuration of the application. It works as a main representation of the app config."""

    def __init__(
        self,
        *,
        init_value: typing.Optional[_ConfigImplementation] = None,
        file_obj: typing.Optional[typing.IO[str]] = None,
        property_name: typing.Optional[str] = None
    ):
        """Create a new config.

        :param init_value: initial value
        :param file_obj: optional file object to parse config from. In most cases, if not defined then empty config
        will be created
        :param property_name: optional name of a dict key that will be imported to this configuration from a file.
        If defined then this config will have this key only
        """
        _ConfigStorage.__init__(self)

        self._config = _ConfigImplementation(dict())

        if init_value is not None:
            self.__merge(init_value)

        if file_obj is not None:
            yaml_data = yaml.safe_load(file_obj)
            if property_name is not None:
                yaml_data = {property_name: yaml_data[property_name]}

            self.__merge(_ConfigImplementation(yaml_data))

    @verify_value(value=lambda x: x.is_dict())
    def __merge(self, value: _ConfigImplementation) -> None:
        """Merge this config with another one.

        :param value: config to merge
        """

        def merge_config(first_config: _ConfigImplementation, second_config: _ConfigImplementation) -> None:
            for property_name, property_value in second_config.dict_iterate():
                impl_property_value = _ConfigImplementation(property_value)
                if not first_config.dict_has(property_name) or not impl_property_value.is_dict():
                    first_config.dict_update(property_name, impl_property_value)
                else:
                    merge_config(first_config.dict_property(property_name), impl_property_value)

        merge_config(self._config, value)

    def properties(self) -> typing.Set[str]:
        """Return keys."""
        return self._config.dict_properties()

    def has_property(self, name: str) -> bool:
        """Check that this configuration has a specified key.

        :param name: key to check
        """
        return self._config.dict_has(name)

    def property(self, name: str) -> typing.Optional[typing.Union['Config', 'ConfigList', 'ConfigOption']]:
        """Return value that is stored within a key.

        :param name: key which value should be retrieved
        """
        property_value = self._config.dict_property(name)
        return _cast_implementation(property_value)

    def __getitem__(self, item: str) -> typing.Optional[typing.Union['Config', 'ConfigList', 'ConfigOption']]:
        """Return value that is stored within a key.

        :param item: key which value should be retrieved
        """
        return self.property(item)

    def reset(self) -> None:
        """Clear this configuration."""
        self._config.dict_clear()

    def merge_file(self, file_obj: typing.IO[str], property_name: typing.Optional[str] = None) -> None:
        """Read config from a file and update this configuration from it.

        :param file_obj: a file to import
        :param property_name: if defined then only this section will be imported from a file
        """
        self.merge_config(Config(file_obj=file_obj, property_name=property_name))

    def merge_config(self, config: 'Config', property_name: typing.Optional[str] = None) -> None:
        """Update this config with another one.

        :param config: a config to read
        :param property_name: if defined then only this section will be imported from a config
        """
        raw_config = config._config
        if property_name is not None:
            if not raw_config.dict_has(property_name):
                raise ValueError(f'There is no {property_name} property in a configuration object')
            raw_config = _ConfigImplementation({property_name: raw_config.dict_property(property_name)})
        self.__merge(raw_config)


class ConfigOption(_ConfigStorage):
    """Represents a single option inside a config."""

    @verify_type(value=(None, str, int, float, bool, _ConfigImplementation))
    @verify_value(value=lambda x: x is not isinstance(x, _ConfigImplementation) or x.is_plain() or x.is_null())
    def __init__(self, value: typing.Union[RawConfigPlainTypes, _ConfigImplementation]) -> None:
        """Create a plain option of configuration.

        :param value: initial value
        """
        _ConfigStorage.__init__(self)

        self._config = _ConfigImplementation(value)

    def option_type(self) -> typing.Optional[type]:
        """Return internal object type."""
        return self._config.raw_type()

    def is_none(self) -> bool:
        """Return True if internal object is None."""
        return self._config.is_none()

    def __str__(self) -> str:
        """Return option's value if it is a string and raise exception otherwise."""
        return str(self._config)

    def __int__(self) -> int:
        """Return option's value if it is an integer and raise exception otherwise."""
        return int(self._config)

    def __float__(self) -> float:
        """Return option's value if it is an floating point number and raise exception otherwise."""
        return float(self._config)

    def __bool__(self) -> bool:
        """Return option's value if it is an boolean and raise exception otherwise."""
        return bool(self._config)


class ConfigList(_ConfigStorage):
    """List-a-like configuration of the application."""

    @verify_value(value=lambda x: x is None or x.is_list())
    def __init__(self, value: typing.Optional[_ConfigImplementation] = None) -> None:
        """Create list-a-like config."""
        _ConfigStorage.__init__(self)
        self._config = value if value is not None else _ConfigImplementation([])

    @verify_type(item=int)
    def __getitem__(self, item: int) -> typing.Optional[typing.Union[Config, 'ConfigList', ConfigOption]]:
        """Return item from internal storage by an index.

        :param item: index of object to retrieve
        """
        return _cast_implementation(self._config.list_get(item))

    def iterate(self) -> typing.Generator[
        typing.Optional[typing.Union[Config, 'ConfigList', ConfigOption]],
        None,
        None
    ]:
        """Iterate over internal storage items."""
        for i in self._config.list_iterate():
            yield _cast_implementation(i)


@verify_type(value=_ConfigImplementation)
def _cast_implementation(value: _ConfigImplementation) -> typing.Union[Config, ConfigList, ConfigOption]:
    """Return internal config representation as "public" objects.

    :param value: internal representation of configuration
    """
    if value.is_none():
        return ConfigOption(None)

    if value.is_dict():
        return Config(init_value=value)

    if value.is_list():
        return ConfigList(value)

    assert(value.is_plain())
    return ConfigOption(value)
