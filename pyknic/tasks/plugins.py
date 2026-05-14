# -*- coding: utf-8 -*-
# pyknic/tasks/plugins.py
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

# TODO: write tests for the code

import importlib.metadata
import typing

from pyknic.lib.log import Logger
from pyknic.lib.tasks.scheduler.chain_source import ChainedTask, __default_chained_tasks_registry__
from pyknic.lib.registry import register_api
from pyknic.environment import PyknicEnvVars


@register_api(__default_chained_tasks_registry__, "plugins_task")
class PluginLoaderTask(ChainedTask):
    """ This task loads plugins
    """

    __entrypoint_group__ = "pyknic.plugins"

    def start(self) -> None:
        """ Initialize plugins
        """

        self.wait_for('log_task')
        Logger.info('Reading information about plugins')

        env_vars_settings = PyknicEnvVars()

        all_env_plugins = env_vars_settings.plugins
        if all_env_plugins:
            for env_plugin in all_env_plugins.split(','):
                self.__load_module_plugin(env_plugin)

        Logger.info('Plugins defined with environment variable were loaded')

        for entry_point_plugin in importlib.metadata.entry_points(group=self.__entrypoint_group__):
            self.__load_entrypoint_plugin(entry_point_plugin)

        Logger.info('Plugins defined with entrypoint were loaded')

    def __load_module_plugin(self, plugin_def: str) -> None:
        try:
            module_name, func_name = plugin_def.split(':')
        except ValueError:
            Logger.error(f'Unable to find module and function of a plugin -- {plugin_def}')
            return

        Logger.info(f'Loading plugin, module: {module_name}, function: {func_name}')

        # if it fails so let it be
        module = importlib.import_module(module_name)
        func = getattr(module, func_name)
        func()

    def __load_entrypoint_plugin(self, plugin: importlib.metadata.EntryPoint) -> None:
        distr = f'"{plugin.dist.name}"' if plugin.dist is not None else 'unknown'
        Logger.info(f'Loading entrypoint plugin: "{plugin.name}" (the distribution is {distr}')

        # if it fails so let it be
        plugin_function = plugin.load()
        plugin_function()

    def task_name(self) -> str:
        """ Return this task's name
        """
        return "plugins-loader"

    @classmethod
    def dependencies(cls) -> typing.Optional[typing.Set[str]]:
        """ The :meth:`.ChainedTask.dependencies` method implementation
        """
        return {"log_task"}
