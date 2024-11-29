# -*- coding: utf-8 -*-
# pyknic/lib/gettext.py
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

import functools
import gettext
import pathlib


class GetTextWrapper:
    """ This class wraps base input parameters for gettext calls. It simplifies and shortens gettext usage
    """

    def __init__(self, translations_path: pathlib.Path):
        """ Create a wrapper with translations in a specified path

        :param translations_path: directory with language subdirectories
        """
        self.__loc_path = translations_path

    def lang(self, lang_name: str) -> gettext.GNUTranslations | gettext.NullTranslations:
        """ Return translation for a specified language

        :param lang_name: language to return
        """
        return self.translation(lang_name, str(self.__loc_path))

    def __call__(self, lang_name: str) -> gettext.GNUTranslations | gettext.NullTranslations:
        """ Synonym for the :meth:`.GetTextWrapper.lang` method call
        """
        return self.lang(lang_name)

    @staticmethod
    @functools.cache
    def translation(lang_name: str, localedir: str) -> gettext.GNUTranslations | gettext.NullTranslations:
        """ Return a translation for a specified language and directory

        :param lang_name: language to use
        :param localedir: directory with language subdirectories
        """
        return gettext.translation("messages", localedir=localedir, languages=[lang_name], fallback=True)
