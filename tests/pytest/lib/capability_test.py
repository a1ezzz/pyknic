# -*- coding: utf-8 -*-

import pytest
import typing

from decorator import decorator

from pyknic.lib.capability import CapabilityDescriptor, capability, CapabilitiesHolderMeta, iscapable
from pyknic.lib.capability import CapabilitiesHolder

from pyknic.lib.typing import GenericFunc, P, R


class TestCapabilityDescriptor:

    def test(self) -> None:
        class A:
            pass

        d = CapabilityDescriptor(A, 'foo')
        assert(d.cls() is A)
        assert(d.name() == 'foo')


class TestCapabilitiesHolderMeta:

    @staticmethod
    def dumb_decorator(f: GenericFunc[P, R]) -> GenericFunc[P, R]:
        def decorator_fn(f: typing.Any, *args: typing.Any, **kwargs: typing.Any) -> typing.Any:
            return f(*args, **kwargs)

        return decorator(decorator_fn)(f)

    def test(self) -> None:

        class A(metaclass=CapabilitiesHolderMeta):

            @capability
            def foo(self) -> int:
                return 1

            def bar(self) -> int:
                return 2

        with pytest.raises(TypeError):
            class B(metaclass=CapabilitiesHolderMeta):
                @classmethod
                @capability
                def foo(cls) -> int:
                    return 1

    def test_iscapable(self) -> None:
        class A(metaclass=CapabilitiesHolderMeta):

            @TestCapabilitiesHolderMeta.dumb_decorator
            @capability
            def foo(self) -> int:
                return 1

            @capability
            @TestCapabilitiesHolderMeta.dumb_decorator
            def bar(self) -> int:
                return 2

            def zzz(self) -> int:
                return 3

        class B(A):

            def foo(self) -> int:
                return 4

        class C(A):

            def bar(self) -> int:
                return 5

        class D(A):

            def foo(self) -> int:
                return 6

            def bar(self) -> int:
                return 7

        a = A()
        b = B()
        c = C()
        d = D()

        assert(a.foo() == 1)
        assert(a.bar() == 2)
        assert(a.zzz() == 3)

        assert(b.foo() == 4)
        assert(b.bar() == 2)
        assert(b.zzz() == 3)

        assert(c.foo() == 1)
        assert(c.bar() == 5)
        assert(c.zzz() == 3)

        assert(d.foo() == 6)
        assert(d.bar() == 7)
        assert(d.zzz() == 3)

        assert(iscapable(A, A.foo) is False)
        assert(iscapable(A, A.bar) is False)
        assert(iscapable(A, B.bar) is False)
        assert(iscapable(A, C.foo) is False)

        assert(iscapable(a, A.foo) is False)
        assert(iscapable(a, A.bar) is False)
        assert(iscapable(a, B.bar) is False)
        assert(iscapable(a, C.foo) is False)

        assert(iscapable(B, A.foo) is True)
        assert(iscapable(B, A.bar) is False)
        assert(iscapable(B, B.bar) is False)
        assert(iscapable(B, C.foo) is True)

        assert(iscapable(b, A.foo) is True)
        assert(iscapable(b, A.bar) is False)
        assert(iscapable(b, B.bar) is False)
        assert(iscapable(b, C.foo) is True)

        assert(iscapable(C, A.foo) is False)
        assert(iscapable(C, A.bar) is True)
        assert(iscapable(C, B.bar) is True)
        assert(iscapable(C, C.foo) is False)

        assert(iscapable(c, A.foo) is False)
        assert(iscapable(c, A.bar) is True)
        assert(iscapable(c, B.bar) is True)
        assert(iscapable(c, C.foo) is False)

        assert(iscapable(D, A.foo) is True)
        assert(iscapable(D, A.bar) is True)
        assert(iscapable(D, B.bar) is True)
        assert(iscapable(D, C.foo) is True)

        assert(iscapable(d, A.foo) is True)
        assert(iscapable(d, A.bar) is True)
        assert(iscapable(d, B.bar) is True)
        assert(iscapable(d, C.foo) is True)


class TestCapabilitiesHolder:

    def test(self) -> None:
        assert(isinstance(CapabilitiesHolder, CapabilitiesHolderMeta) is True)

        class A(CapabilitiesHolder):
            @capability
            def foo(self) -> None:
                pass

            @capability
            def bar(self) -> None:
                pass

        class B(A):
            pass

        class C(A):

            def foo(self) -> None:
                pass

        a = A()
        b = B()
        c = C()

        assert(iscapable(a, A.foo) is False)
        assert(iscapable(b, A.foo) is False)
        assert(iscapable(c, A.foo) is True)

        assert(iscapable(A, A.foo) is False)
        assert(iscapable(B, A.foo) is False)
        assert(iscapable(C, A.foo) is True)

        assert(iscapable(a, A.bar) is False)
        assert(iscapable(b, A.bar) is False)
        assert(iscapable(c, A.bar) is False)

        assert(iscapable(A, A.bar) is False)
        assert(iscapable(B, A.bar) is False)
        assert(iscapable(C, A.bar) is False)

        assert(A.foo not in a)
        assert(A.foo not in b)
        assert(A.foo in c)

        assert(A.bar not in a)
        assert(A.bar not in a)
        assert(A.bar not in a)

        class D(CapabilitiesHolder):
            @capability
            def foo(self) -> None:
                pass

            @capability
            def bar(self) -> None:
                pass

        assert(iscapable(c, D.foo) is False)
        assert(D.foo not in c)
