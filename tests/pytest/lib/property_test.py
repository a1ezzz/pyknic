# -*- coding: utf-8 -*-

import pytest

from pyknic.lib.property import TypedDescriptor


class TestTypedDescriptor:

    def test(self) -> None:

        class A:
            prop_a = TypedDescriptor(int)

        a = A()
        assert(a.prop_a is None)

        a.prop_a = 10
        assert(a.prop_a == 10)

        with pytest.raises(TypeError):
            a.prop_a = 'foo'  # type: ignore[assignment]   # it is a test by itself

    def test_default(self) -> None:

        class A:
            prop_a = TypedDescriptor(int, 10)

        a = A()
        assert(a.prop_a == 10)

        with pytest.raises(TypeError):
            class B:
                prop_a = TypedDescriptor(int, 'foo')

    def test_verifier(self) -> None:
        class A:
            prop_a = TypedDescriptor(int, value_verifier=lambda x: x is None or x > 10)

        a = A()
        assert(a.prop_a is None)

        a.prop_a = 11
        assert(a.prop_a == 11)
        with pytest.raises(ValueError):
            a.prop_a = 10

        with pytest.raises(ValueError):
            class B:
                prop_a = TypedDescriptor(int, default_value=10, value_verifier=lambda x: x is None or x > 10)

    def test_exceptions(self) -> None:
        # unusual and strange property usage; so it is coverage-related test
        obj = object()
        prop = TypedDescriptor(int)
        with pytest.raises(TypeError):
            prop.__get__(obj)

        with pytest.raises(TypeError):
            prop.__set__(obj, 10)
