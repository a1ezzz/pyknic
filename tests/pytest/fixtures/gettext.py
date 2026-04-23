# -*- coding: utf-8 -*-

import pytest

from pyknic.lib.gettext import GetTextWrapper
from pyknic.lib.path import root_path


@pytest.fixture
def gettext() -> GetTextWrapper:
    return GetTextWrapper(root_path / 'locales')
