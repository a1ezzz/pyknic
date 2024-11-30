# -*- coding: utf-8 -*-

import pytest

from pyknic.path import root_path
from pyknic.lib.gettext import GetTextWrapper


@pytest.fixture
def gettext() -> GetTextWrapper:
    return GetTextWrapper(root_path / 'locales')
