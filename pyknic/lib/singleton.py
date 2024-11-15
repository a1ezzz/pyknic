# -*- coding: utf-8 -*-
# pyknic/lib/singleton.py
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

import typing

from abc import ABCMeta


class SingletonMeta(ABCMeta):
    """ This metaclass helps to implement a transparent globally accepted instance (singleton)
    """

    __instance__ = None  # singleton instance

    def __init__(cls, name: str, bases: typing.Tuple[type], namespace: typing.Dict[str, typing.Any]):
        """ Create a new instance
        """
        ABCMeta.__init__(cls, name, bases, namespace)

    def __getattribute__(cls, item: str) -> typing.Any:
        """ Try to get attribute from an instance
        """
        if item == "__instance__":
            return ABCMeta.__getattribute__(cls, item)

        if cls.__instance__ is not None and item in dir(cls.__instance__):
            return cls.__instance__.__getattribute__(item)

        return ABCMeta.__getattribute__(cls, item)

    def __setattr__(cls, key: str, value: typing.Any) -> None:
        """ Try to set attribute for an instance
        """
        if cls.__instance__ is not None and key in dir(cls.__instance__):
            cls.__instance__.__setattr__(key, value)
        else:
            ABCMeta.__setattr__(cls, key, value)

    def setup_singleton(cls, value: typing.Any) -> None:
        """ Setup an instance as a singleton. Each instance may be set up only once
        """
        if cls.__instance__ is not None:
            raise ValueError('Singleton has been initialized already')
        cls.__instance__ = value

    def singleton(cls) -> typing.Any:
        """ Return an instance or None if an instance has not been set up
        """
        return cls.__instance__


def create_singleton(value: typing.Any) -> type:
    """ Return initialized singleton class

    :param value: value to set up a singleton
    """
    class Singleton(metaclass=SingletonMeta):
        __instance__ = value
    return Singleton
