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

from pyknic.lib.capability import CapabilitiesHolder, capability
from pyknic.lib.verify import verify_type, verify_value


class ConfigStorageProto(CapabilitiesHolder):
    """This class is used mostly by mypy to detect possible methods and results of methods. It is
    full of "capabilities" that are implemented in some classes and not in others.

    In a real implementation each object is similar to one of:
     - dict
     - list
     - str
     - bool
     - int
     - float
     - None
    and implement related methods only
    """

    @capability
    def getitem(self, item: typing.Union[str, int]) -> 'ConfigStorageProto':
        """Return value that is stored within a key, or get a value by an index (a real behaviour depends on
        implementation).

        :param item: key (index) which value should be retrieved
        """
        raise NotImplementedError('This method is abstract')

    def __getitem__(self, item: typing.Union[str, int]) -> 'ConfigStorageProto':
        """Shortcut for the :meth:`.ConfigStorageProto.getitem` capability."""
        return self.getitem(item)

    @capability
    def as_int(self) -> int:
        """If possible return integer value of this config. Suitable for a plain, non-aggregated entries."""
        raise NotImplementedError('This method is abstract')

    def __int__(self) -> int:
        """Shortcut for the :meth:`.ConfigStorageProto.as_int` capability."""
        return self.as_int()

    @capability
    def as_float(self) -> float:
        """If possible return floating point value of this config. Suitable for a plain, non-aggregated entries."""
        raise NotImplementedError('This method is abstract')

    def __float__(self) -> float:
        """Shortcut for the :meth:`.ConfigStorageProto.as_float` capability."""
        return self.as_float()

    @capability
    def as_bool(self) -> bool:
        """If possible return boolean value of this config. Suitable for a plain, non-aggregated entries."""
        raise NotImplementedError('This method is abstract')

    def __bool__(self) -> bool:
        """Shortcut for the :meth:`.ConfigStorageProto.as_bool` capability."""
        return self.as_bool()

    @capability
    def as_str(self) -> str:
        """If possible return string value of this config. Suitable for a plain, non-aggregated entries."""
        raise NotImplementedError('This method is abstract')

    def __str__(self) -> str:
        """Shortcut for the :meth:`.ConfigStorageProto.as_str` capability."""
        return self.as_str()

    @capability
    def is_none(self) -> bool:
        """Return True if this option is defined as None. Suitable for a plain, non-aggregated entries."""
        raise NotImplementedError('This method is abstract')

    @capability
    def properties(self) -> typing.Set[str]:
        """Return keys that this dict-a-like aggregator holds"""
        raise NotImplementedError('This method is abstract')

    @capability
    def has_property(self, name: str) -> bool:
        """Return True if this dict-a-like aggregator holds the specified key

        :param name: a key name to check
        """
        raise NotImplementedError('This method is abstract')

    @capability
    def property(self, name: str) -> 'ConfigStorageProto':
        """Return True if this dict-a-like aggregator holds the specified key

        :param name: a key name to check
        """
        raise NotImplementedError('This method is abstract')

    @capability
    def reset_properties(self) -> None:
        """Remove everything that this dict-a-like aggregator holds."""
        raise NotImplementedError('This method is abstract')

    @capability
    def merge_file(self, file_obj: typing.IO[str], property_name: typing.Optional[str] = None) -> None:
        """Union this dict-a-like configuration with another one.

        :param file_obj: file object to merge
        :param property_name: if defined then only this section will be imported from a file
        """
        raise NotImplementedError('This method is abstract')

    @capability
    def merge_config(self, config: 'ConfigStorageProto', property_name: typing.Optional[str] = None) -> None:
        """Union this dict-a-like configuration with another one.

        :param config: a config to read
        :param property_name: if defined then only this section will be imported from a config
        """
        raise NotImplementedError('This method is abstract')

    @capability
    def iterate_list(self) -> typing.Generator['ConfigStorageProto', None, None]:
        """Iterate over list-a-like configuration."""
        raise NotImplementedError('This method is abstract')


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


class _ConfigStorage(ConfigStorageProto):
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

            if yaml_data is not None:
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
        """:meth:`.ConfigStorageProto.properties` implementation"""
        return self._config.dict_properties()

    def has_property(self, name: str) -> bool:
        """:meth:`.ConfigStorageProto.has_property` implementation"""
        return self._config.dict_has(name)

    def property(self, name: str) -> ConfigStorageProto:
        """:meth:`.ConfigStorageProto.property` implementation"""
        property_value = self._config.dict_property(name)
        return _cast_implementation(property_value)

    @verify_type(item=str)
    def __getitem__(self, item: typing.Union[str, int]) -> ConfigStorageProto:
        """:meth:`.ConfigStorageProto.__getitem__` implementation"""
        return self.property(item)  # type: ignore[arg-type]  # verify_type do the job

    def reset_properties(self) -> None:
        """:meth:`.ConfigStorageProto.reset_properties` implementation"""
        self._config.dict_clear()

    def merge_file(self, file_obj: typing.IO[str], property_name: typing.Optional[str] = None) -> None:
        """:meth:`.ConfigStorageProto.merge_file` implementation"""
        self.merge_config(Config(file_obj=file_obj, property_name=property_name))

    def merge_config(self, config: 'ConfigStorageProto', property_name: typing.Optional[str] = None) -> None:
        """:meth:`.ConfigStorageProto.merge_config` implementation"""
        if not isinstance(config, Config):
            raise TypeError('Unable to merge with non-Config instance')

        raw_config = config._config
        if property_name is not None:
            if not raw_config.dict_has(property_name):
                raise ValueError(f'There is no {property_name} property in a configuration object')
            raw_config = _ConfigImplementation({property_name: raw_config.dict_property(property_name)})
        self.__merge(raw_config)


class ConfigList(_ConfigStorage):
    """List-a-like configuration of the application."""

    @verify_value(value=lambda x: x is None or x.is_list())
    def __init__(self, value: typing.Optional[_ConfigImplementation] = None) -> None:
        """Create list-a-like config."""
        _ConfigStorage.__init__(self)
        self._config = value if value is not None else _ConfigImplementation([])

    @verify_type(item=int)
    def __getitem__(self, item: typing.Union[int, str]) -> ConfigStorageProto:
        """:meth:`.ConfigStorageProto.__getitem__` implementation"""
        return _cast_implementation(self._config.list_get(item))  # type: ignore[arg-type]  # verify_type do the job

    def iterate_list(self) -> typing.Generator[ConfigStorageProto, None, None]:
        """:meth:`.ConfigStorageProto.iterate_list` implementation"""
        for i in self._config.list_iterate():
            yield _cast_implementation(i)


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

    def is_none(self) -> bool:
        """:meth:`.ConfigStorageProto.is_none` implementation"""
        return self._config.is_none()

    def as_str(self) -> str:
        """:meth:`.ConfigStorageProto.as_str` implementation"""
        return str(self._config)

    def as_int(self) -> int:
        """:meth:`.ConfigStorageProto.as_int` implementation"""
        return int(self._config)

    def as_float(self) -> float:
        """:meth:`.ConfigStorageProto.as_float` implementation"""
        return float(self._config)

    def as_bool(self) -> bool:
        """:meth:`.ConfigStorageProto.as_bool` implementation"""
        return bool(self._config)


@verify_type(value=_ConfigImplementation)
def _cast_implementation(value: _ConfigImplementation) -> ConfigStorageProto:
    """Cast internal config representation to "public" objects.

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
