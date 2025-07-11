# -*- coding: utf-8 -*-

from pyknic.lib.fastapi.lobby_commands.resources import ResourcesCommand
from pyknic.lib.fastapi.models.lobby import LobbyCommandRequest


class TestResourcesCommand:

    def test(self) -> None:
        ResourcesCommand.exec(LobbyCommandRequest(name=ResourcesCommand.command_name()))
