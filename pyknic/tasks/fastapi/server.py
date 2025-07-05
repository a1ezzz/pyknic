# -*- coding: utf-8 -*-
# pyknic/tasks/fastapi/server.py
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

# TODO: document the code
# TODO: write tests for the code
# TODO: tweak uvicorn logger settings

import asyncio
import uuid

import fastapi
import typing
import uvicorn

from dataclasses import dataclass

from pyknic.lib.datalog.proto import DatalogProto
from pyknic.lib.tasks.scheduler.chain_source import ChainedTask, __default_chained_tasks_registry__
from pyknic.lib.fastapi.apps_registry import __default_fastapi_apps_registry__
from pyknic.lib.registry import register_api

from pyknic.lib.log import Logger


@dataclass
class FastAPIServer:
    fastapi_app: fastapi.FastAPI
    uvicorn_server: uvicorn.Server


@register_api(__default_chained_tasks_registry__, "fastapi-init")
class FastAPIInitTask(ChainedTask):

    def start(self) -> None:
        """ The :meth:`.TaskProto.start` method implementation
        """
        Logger.info('Check dependencies')

        self.wait_for('log_task')
        config = self.wait_for('config_task').result  # type: ignore[union-attr]

        Logger.info('Prepare fastAPI')

        config_section = config["pyknic"]["fastapi"]

        docs_url = '/docs' if bool(config_section["swagger"]) else None
        redoc_url = '/redoc' if bool(config_section["redoc"]) else None
        openapi_url = '/openapi.json' if bool(config_section["openapi"]) else None

        app = fastapi.FastAPI(docs_url=docs_url, redoc_url=redoc_url, openapi_url=openapi_url)  # TODO: check options!
        uvicorn_config = uvicorn.Config(  # TODO: check options!
            app, host=str(config_section["uvicorn_host"]), port=int(config_section["uvicorn_port"])
        )
        uvicorn_server = uvicorn.Server(uvicorn_config)

        self.save_result(FastAPIServer(fastapi_app=app, uvicorn_server=uvicorn_server))

        Logger.info('FastAPI prepared')

    def task_name(self) -> typing.Optional[str]:
        """ The :meth:`.ChainedTask.task_name` method implementation
        """
        return 'fastAPI-init'

    @classmethod
    def dependencies(cls) -> typing.Optional[typing.Set[str]]:
        """ The :meth:`.ChainedTask.dependencies` method implementation
        """
        return {"log_task", "config_task"}


@register_api(__default_chained_tasks_registry__, "fastapi-loader")
class FastAPILoaderTask(ChainedTask):

    def __init__(self, datalog: DatalogProto, api_id: str, uid: uuid.UUID):
        ChainedTask.__init__(self, datalog, api_id, uid)

        # just to be sure that important info will not be compacted by the mighty GC
        self.__loaded_apps: typing.List[typing.Any] = []

    def start(self) -> None:
        """ The :meth:`.TaskProto.start` method implementation
        """
        Logger.info('Populate fastAPI server')

        fastapi_init = self.wait_for('fastapi-init')
        config_result = self.wait_for('config_task')
        gettext_result = self.wait_for('gettext_task')

        assert(fastapi_init)
        assert(config_result)
        assert(gettext_result)

        config = config_result.result

        apps_enabled = [str(x) for x in config["pyknic"]["fastapi"]["apps"]]
        apps_enabled.sort()

        for app_id in apps_enabled:
            Logger.info(f'Reading the app "{app_id}"')
            fastapi_app_cls = __default_fastapi_apps_registry__.get(app_id)
            created_app = fastapi_app_cls.create_app(fastapi_init.result.fastapi_app, config, gettext_result.result)
            if created_app is not None:
                self.__loaded_apps.append(created_app)

    def task_name(self) -> typing.Optional[str]:
        """ The :meth:`.ChainedTask.task_name` method implementation
        """
        return 'fastAPI-loader'

    @classmethod
    def dependencies(cls) -> typing.Optional[typing.Set[str]]:
        """ The :meth:`.ChainedTask.dependencies` method implementation
        """
        return {"fastapi-init", "gettext_task"}


@register_api(__default_chained_tasks_registry__, "fastapi-server")
class FastAPIServerTask(ChainedTask):

    def __init__(self, datalog: DatalogProto, api_id: str, uid: uuid.UUID):
        ChainedTask.__init__(self, datalog=datalog, api_id=api_id, uid=uid)

        self.__loop: asyncio.AbstractEventLoop = asyncio.new_event_loop()
        self.__uvicorn_server: typing.Optional[uvicorn.Server] = None

    async def __stop_request(self) -> None:
        assert(self.__uvicorn_server)

        self.__uvicorn_server.should_exit = True
        await self.__uvicorn_server.shutdown()

    def start(self) -> None:
        """ The :meth:`.TaskProto.start` method implementation
        """
        Logger.info('Starting fastAPI')
        assert(self.__loop)

        fastapi_init = self.wait_for('fastapi-init')
        assert(fastapi_init)

        self.__uvicorn_server = fastapi_init.result.uvicorn_server
        self.__loop.run_until_complete(self.__uvicorn_server.serve())

        Logger.info('FastAPI stopped')

    def stop(self) -> None:
        Logger.info('Generate fastAPI stop request')
        future = asyncio.run_coroutine_threadsafe(self.__stop_request(), self.__loop)
        future.result()
        Logger.info('FastAPI stop requested')

    def task_name(self) -> typing.Optional[str]:
        """ The :meth:`.ChainedTask.task_name` method implementation
        """
        return 'fastAPI-server'

    @classmethod
    def dependencies(cls) -> typing.Optional[typing.Set[str]]:
        """ The :meth:`.ChainedTask.dependencies` method implementation
        """
        return {"fastapi-loader"}
