# -*- coding: utf-8 -*-

import typing
import pathlib
import pytest

from pyknic.lib.config import Config


@pytest.fixture
def config_file() -> typing.Callable[[pathlib.Path], Config]:

    def return_config(path):
        config = Config()
        with open(pathlib.Path(__file__).parent / '..' / '..' / '..' / 'pyknic' / path ) as f:
            config.merge_file(f)

        return config

    return return_config
