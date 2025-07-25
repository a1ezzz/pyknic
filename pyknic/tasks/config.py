# -*- coding: utf-8 -*-
# pyknic/tasks/config.py
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

# TODO: write tests for the code

import itertools
import os
import typing

from pyknic.lib.tasks.scheduler.chain_source import ChainedTask, __default_chained_tasks_registry__
from pyknic.lib.registry import register_api

from pyknic.lib.log import Logger
from pyknic.lib.config import Config


@register_api(__default_chained_tasks_registry__, "config_task")
class ConfigTask(ChainedTask):
    """ Generate a configuration

    Configuration is generated by applying multiple files. Files are applied in the following order:
      - default configurations (config.yaml files from the "pyknic.tasks" subdirectories)
      - if the "PYKNIC_APP_DIR_CONFIG" variable is set then read configurations (any file) from this directory
        and its subdirectories
      - if the "PYKNIC_APP_FILE_CONFIG" variable is set then read configuration from this file
    """

    __apps_defaults_dir__ = os.path.join(os.path.dirname(__file__), '..')  # directory with default configurations
    __default_file__ = "config.yaml"  # default configuration file name

    __app_dir_config_envar__ = "PYKNIC_APP_DIR_CONFIG"  # defines an environment variable for directory with configs
    __app_file_config_envar__ = "PYKNIC_APP_FILE_CONFIG"  # defines an environment variable for config file

    def __load_file(self, config: Config, filename: str) -> None:
        """ Merge data from a file to a config

        :param config: a config to merge to
        :param filename: a file that holds data
        """
        if os.path.isfile(filename) is False:
            raise ValueError(f'Invalid configuration (no such file): "{filename}"')

        with open(filename) as f:
            config.merge_file(f)
        Logger.info(f'Configuration loaded from the file: "{os.path.abspath(filename)}"')

    def __check_directory(
        self, config: Config, dir_path: str, file_pattern: typing.Optional[str] = None
    ) -> typing.Set[str]:
        """ List directory and merge found files with a config

        :param config: a config to merge to
        :param dir_path: a directory to search in
        :param file_pattern: if defined only this file will be read from directories

        :return: return absolute paths for found inner directories
        """
        inner_dirs = set()

        for e in os.listdir(dir_path):
            e_path = os.path.join(dir_path, e)
            Logger.debug(f"Checking configuration in the directory \"{os.path.relpath(dir_path)}\" -- {e_path}")

            if os.path.isdir(e_path):
                inner_dirs.add(e_path)
            elif file_pattern is not None and e == file_pattern:
                self.__load_file(config, e_path)
            elif file_pattern is None and os.path.isfile(e_path):
                self.__load_file(config, e_path)

        return inner_dirs

    def __read_directory(self, config: Config, dir_path: str, file_pattern: typing.Optional[str] = None) -> None:
        """ Recursively list directories and merge found files with a config

        :param config: a config to merge to
        :param dir_path: a root directory inside which files will be searched
        :param file_pattern: if defined only this file will be read from directories
        """
        check_dirs = [dir_path]
        while check_dirs:
            check_dirs.sort()
            next_dirs = [self.__check_directory(config, x, file_pattern=file_pattern) for x in check_dirs]
            check_dirs = list(itertools.chain(*next_dirs))  # flatten the list

    def start(self) -> None:
        """ The :meth:`.TaskProto.start` method implementation
        """
        self.wait_for('log_task')
        Logger.info('Reading configuration')

        result = Config()
        self.__read_directory(result, self.__apps_defaults_dir__, self.__default_file__)

        if self.__app_dir_config_envar__ in os.environ:
            self.__read_directory(result, os.environ[self.__app_dir_config_envar__])

        if self.__app_file_config_envar__ in os.environ:
            self.__load_file(result, os.environ[self.__app_file_config_envar__])

        self.save_result(result)
        Logger.info('Configuration loaded')

    def task_name(self) -> typing.Optional[str]:
        """ The :meth:`.ChainedTask.task_name` method implementation
        """
        return 'config-reader'

    @classmethod
    def dependencies(cls) -> typing.Optional[typing.Set[str]]:
        """ The :meth:`.ChainedTask.dependencies` method implementation
        """
        return {"log_task"}
