# -*- coding: utf-8 -*-

from pyknic.lib.gettext import GetTextWrapper
from pyknic.lib.path import root_path


class TestGetTextWrapper:

    def test(self) -> None:
        wrapper = GetTextWrapper(root_path / 'locales')
        assert(wrapper.lang("ru").gettext("Choose a game") == "Выбирай игру")
        assert(wrapper("fr").gettext("Choose a game") == "Choose a game")  # no such translation
        assert(wrapper().gettext("Choose a game") == "Choose a game")  # no such translation
