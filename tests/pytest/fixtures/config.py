# -*- coding: utf-8 -*-

import typing
import pathlib
import pytest

from pyknic.lib.config import Config
from pyknic.path import root_path


@pytest.fixture
def config_file() -> typing.Callable[[pathlib.Path], Config]:

    def return_config(path: pathlib.Path) -> Config:
        config = Config()
        with open(root_path / path) as f:
            config.merge_file(f)

        return config

    return return_config
