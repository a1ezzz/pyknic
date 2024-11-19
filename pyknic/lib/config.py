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

import configparser
import typing
from configparser import ConfigParser


class Config:
    """ Main configuration of the application
    """

    def __init__(self, main_file_obj: typing.Optional[typing.IO[str]] = None, section: typing.Optional[str] = None):
        """ Create a new config

        :param main_file_obj: optional file object to parse config from. If not defined then empty config will be
        created
        :param section: optional name of a section that will be imported to this config from a file. If defined then
        this config will have this section only
        """
        parser = configparser.ConfigParser()
        if main_file_obj is not None:
            parser.read_file(main_file_obj)

        if section is not None:
            for s in filter(lambda x: x != section, parser.sections()):
                parser.remove_section(s)

        self.__parser = parser

    def sections(self) -> typing.Set[str]:
        """ Return sections names
        """
        return set(self.__parser.sections())

    def section(self, section: str, option_prefix: typing.Optional[str] = None) -> 'ConfigSection':
        """ Return one section from this config

        :param section: section to return
        :param option_prefix: if defined then only options that start with this prefix will be accessible
        """
        if not self.has_section(section):
            raise ValueError(f'Config does not have the "{section}" section')
        return ConfigSection(self, self.__parser, section, option_prefix=option_prefix)

    def __getitem__(self, item: str) -> 'ConfigSection':
        """ Return a section with all the options
        """
        return self.section(item)

    def has_section(self, section: str) -> bool:
        """ Return True if the specified section exists inside this config and return False otherwise

        :param section: a name of a section to check
        """
        return self.__parser.has_section(section)

    def has_option(self, section: str, option: str) -> bool:
        """ Return True if this config has an option inside a section and return False otherwise

        :param section: a name of a section to check
        :param option: a name of an option to check
        """
        if self.has_section(section) is False:
            return False
        return self.section(section).has_option(option)

    def reset(self) -> None:
        """ Clear this configuration
        """
        for s in self.__parser.sections():
            self.__parser.remove_section(s)

    def merge_file(self, file_obj: typing.IO[str], section: typing.Optional[str] = None) -> None:
        """ Read config from a file and update this configuration from it

        :param file_obj: a file to import
        :param section: if defined then only this section will be imported from a file
        """
        self.merge_config(Config(file_obj, section=section))

    def merge_config(self, config: 'Config', section: typing.Optional[str] = None) -> None:
        """ Update this config with another one

        :param config: a config to read
        :param section: if defined then only this section will be imported from a config
        """
        def merge_section(section_name: str) -> None:
            if not self.__parser.has_section(section_name):
                self.__parser.add_section(section_name)

            config_section = config[section_name]
            for option in config_section.options():
                self.__parser.set(section_name, option, config_section[option].raw())

        if section is not None:
            if config.has_section(section) is False:
                raise ValueError(f'Merged config does not have the "{section}" section')
            merge_section(section)
            return

        for s in config.sections():
            merge_section(s)

    def sections_subset(self, sections_prefix: str) -> 'Config':
        """ Return a copy of this config but only with those sections whose names are started with a parameter

        :param sections_prefix: a prefix to check
        """
        config = Config()

        for section in filter(lambda x: x.startswith(sections_prefix), self.sections()):
            config.merge_config(self, section)

        return config


class ConfigSection:
    """ This class represents a single section from a config
    """

    def __init__(
        self, config: Config, parser: ConfigParser, section: str, option_prefix: typing.Optional[str] = None
    ) -> None:
        """ Create a section

        :param config: a section origin
        :param parser: an inside parser that hold configuration
        :param section: a name of a section this class represents
        :param option_prefix: optional prefix that limits accessible options, only those options that are started
        with this prefix may be read
        """
        self.__config = config
        self.__parser = parser
        self.__section = section
        self.__option_prefix = option_prefix

    def __option(self, name: str) -> str:
        """ Return a full option name

        :param name: a base name for which a full option name should be returned
        """
        return name if self.__option_prefix is None else (self.__option_prefix + name)

    def config(self) -> Config:
        """ Return a section origin
        """
        return self.__config

    def section(self) -> str:
        """ Return a section name
        """
        return self.__section

    def options_prefix(self) -> typing.Optional[str]:
        """ Return prefix of options if it was defined
        """
        return self.__option_prefix

    def options(self) -> typing.Set[str]:
        """ Return set of available options (with respect to a prefix, if it was defined)
        """
        return set(self.__parser.options(self.__section))

    def has_option(self, option_name: str) -> bool:
        """ Return True if the specified option exists and return False otherwise

        :param option_name: a name of an option to check
        """
        return self.__parser.has_option(self.__section, self.__option(option_name))

    def option(self, option: str) -> 'ConfigOption':
        """ Return an option by its name

        :param option: a name of an option to return
        """
        return ConfigOption(self.__config, self.__parser, self.__section, self.__option(option))

    def __getitem__(self, item: str) -> 'ConfigOption':
        """ Return an option by its name

        :param item: a name of an option to return
        """
        return self.option(item)


class ConfigOption:
    """ Represents a single option inside a config
    """

    def __init__(self, config: Config, parser: ConfigParser, section: str, option: str):
        """ Create an option

        :param config: origin config
        :param parser: an inside parser that hold configuration
        :param section: a name of a section this class represents
        :param option: a name of an option this class represents
        """
        self.__config = config
        self.__parser = parser
        self.__section = section
        self.__option = option

    def config(self) -> Config:
        """ Return an option origin
        """
        return self.__config

    def section(self) -> str:
        """ Return an option origin
        """
        return self.__section

    def option(self) -> str:
        """ Return a name of this option
        """
        return self.__option

    def __str__(self) -> str:
        """ Return string representation of an option's value
        """
        return self.__parser.get(self.__section, self.__option)

    def __int__(self) -> int:
        """ Return integer representation of an option's value
        """
        return self.__parser.getint(self.__section, self.__option)

    def __float__(self) -> float:
        """ Return float representation of an option's value
        """
        return self.__parser.getfloat(self.__section, self.__option)

    def __bool__(self) -> bool:
        """ Return boolean representation of an option's value
        """
        return self.__parser.getboolean(self.__section, self.__option)

    def raw(self) -> str:
        """ Return option's value without interpolation
        """
        return self.__parser.get(self.__section, self.__option, raw=True)
