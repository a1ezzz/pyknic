# -*- coding: utf-8 -*-

import pytest
import typing

from abc import ABCMeta

from pyknic.lib.singleton import SingletonMeta, create_singleton


class TestSingletonMeta:

    def test(self) -> None:

        class BaseClass:
            def __init__(self, x: int) -> None:
                self.x = x

            def pow(self, y: int) -> typing.Any:
                return self.x ** y

        class SingletonClass(metaclass=SingletonMeta):
            pass

        value = BaseClass(5)
        assert(SingletonClass.singleton() is None)
        SingletonClass.setup_singleton(value)
        assert(SingletonClass.singleton() is value)

        with pytest.raises(ValueError):
            SingletonClass.setup_singleton(BaseClass(6))

        assert(SingletonClass.x == 5)
        assert(SingletonClass.pow(2) == 25)

        SingletonClass.x = 7
        assert(SingletonClass.pow(2) == 49)


def test_create_singleton() -> None:
    class BaseClass:
        pass

    value = BaseClass()
    singleton = create_singleton(value)
    assert(isinstance(singleton, SingletonMeta))
    assert(ABCMeta.__getattribute__(singleton, "__instance__") is value)
