# -*- coding: utf-8 -*-

from pyknic.path import root_path
from pyknic.lib.gettext import GetTextWrapper


class TestGetTextWrapper:

    def test(self) -> None:
        wrapper = GetTextWrapper(root_path / 'locales')
        assert(wrapper.lang("ru").gettext("Choose a game") == "Выбирай игру")
        assert(wrapper("fr").gettext("Choose a game") == "Choose a game")  # no such translation
