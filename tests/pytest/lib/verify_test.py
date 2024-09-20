# -*- coding: utf-8 -*-

import typing
import pytest

from inspect import isfunction

from pyknic.lib.verify import Verifier, TypeVerifier, SubclassVerifier, ValueVerifier
from pyknic.lib.verify import verify_value, verify_type, verify_subclass


def sample_function(
    a: typing.Any, b: typing.Any, c: typing.Any, d: typing.Optional[typing.Any] = None, **kwargs: typing.Any
) -> None:
    """ function info """
    pass


class TestVerifier:

    class FNameChecker:

        @staticmethod
        def foo() -> None:
            pass

        @classmethod
        def bar(cls) -> None:
            pass

        def zzz(self) -> None:
            pass

        def __call__(self) -> None:
            pass

    def test_check(self) -> None:
        check = Verifier().check(None, '', lambda x: None)
        assert(isfunction(check) is True)

    def test_decorator(self) -> None:

        verifier = Verifier()

        assert(verifier.decorator()(sample_function) != sample_function)
        verifier = Verifier()

        def exc() -> None:
            raise TypeError('text exception')

        default_check = lambda x: None  # noqa: E731
        exc_check = lambda x: exc() if x == 3 else None  # noqa: E731
        a_spec = lambda x: 111  # noqa: E731
        override_check = lambda s, n, f: exc_check if n == 'a' or n == 'd' or n == 'e' else default_check  # noqa: E731
        verifier.check = override_check  # type: ignore[method-assign] # just an ugly test
        decorated_fn = verifier.decorator(a=a_spec, c=1, d=1, e=1)(sample_function)

        decorated_fn(1, 2, 3, d=4)
        pytest.raises(TypeError, decorated_fn, 3, 2, 3, d=4)
        pytest.raises(TypeError, decorated_fn, 1, 2, 3, d=3)
        decorated_fn(1, 2, 3, d=4, e=5)
        pytest.raises(TypeError, decorated_fn, 1, 2, 3, d=4, e=3)

    def test_function_name(self) -> None:

        assert(Verifier.function_name(TestVerifier.FNameChecker.foo) == 'TestVerifier.FNameChecker.foo')
        assert(Verifier.function_name(TestVerifier.FNameChecker.bar) == 'TestVerifier.FNameChecker.bar')
        assert(Verifier.function_name(TestVerifier.FNameChecker.zzz) == 'TestVerifier.FNameChecker.zzz')
        assert(Verifier.function_name(TestVerifier.FNameChecker) == 'TestVerifier.FNameChecker')

        c = TestVerifier.FNameChecker()
        assert(Verifier.function_name(c.foo) == 'TestVerifier.FNameChecker.foo')
        assert(Verifier.function_name(c.bar) == 'TestVerifier.FNameChecker.bar')
        assert(Verifier.function_name(c.zzz) == 'TestVerifier.FNameChecker.zzz')
        assert(isinstance(Verifier.function_name(c), str))  # we have a result but with random id


class TestTypeVerifier:

    def test_check(self) -> None:
        verifier = TypeVerifier()

        with pytest.raises(RuntimeError):
            verifier.decorator(a=None)(sample_function)

        with pytest.raises(RuntimeError):
            verifier.decorator(a=(str, None, 1))(sample_function)

        decorated_fn = verifier.decorator(
            a=int, b=(str, None), c=[str, int], d=(str, int, None), e=float
        )(sample_function)
        decorated_fn(1, None, 'f')
        decorated_fn(1, None, 1, d='o')
        decorated_fn(1, None, 'o', d=5, e=.1)

        with pytest.raises(TypeError):
            decorated_fn('b', None, 'f')

        with pytest.raises(TypeError):
            decorated_fn(1, 4, 'o')

        with pytest.raises(TypeError):
            decorated_fn(1, None, None)

        with pytest.raises(TypeError):
            decorated_fn(1, None, 'o', d=.1)

        with pytest.raises(TypeError):
            decorated_fn(1, None, 'b', e='a')

        def foo(*args: typing.Any) -> None:
            pass

        decorated_foo = verifier.decorator(args=int)(foo)
        decorated_foo()
        decorated_foo(1, 2, 3)
        pytest.raises(TypeError, decorated_foo, 0.1)
        pytest.raises(TypeError, decorated_foo, 1, 0.1, 4)

        def bar(x: typing.Any, *args: typing.Any) -> None:
            pass

        decorated_bar = verifier.decorator(args=(int, float))(bar)
        decorated_bar('')
        decorated_bar('', 0.1, 2, 3)
        pytest.raises(TypeError, decorated_bar, '', '')


class TestSubclassVerifier:

    def test_check(self) -> None:
        verifier = SubclassVerifier()

        with pytest.raises(RuntimeError):
            verifier.decorator(a=None)(sample_function)

        with pytest.raises(RuntimeError):
            verifier.decorator(a=(str, None, 1))(sample_function)

        class A:
            pass

        class B(A):
            pass

        class C(A):
            pass

        class D:
            pass

        decorated_fn = verifier.decorator(a=A, c=(B, C), d=[B, None], e=C)(sample_function)
        decorated_fn(A, None, B)
        decorated_fn(B, None, B)
        decorated_fn(A, None, B, d=B)
        decorated_fn(A, None, C, d=B)
        decorated_fn(A, None, B, d=None, e=C)

        with pytest.raises(TypeError):
            decorated_fn(D, None, B)

        with pytest.raises(TypeError):
            decorated_fn(A, None, A)

        with pytest.raises(TypeError):
            decorated_fn(A, None, None)

        with pytest.raises(TypeError):
            decorated_fn(A, None, B, d=C)

        with pytest.raises(TypeError):
            decorated_fn(A, None, B, d=B, e=A)


class TestValueVerifier:

    def test_check(self) -> None:

        verifier = ValueVerifier()

        with pytest.raises(RuntimeError):
            verifier.decorator(a=1)(sample_function)

        with pytest.raises(RuntimeError):
            verifier.decorator(a=(1,))(sample_function)

        decorated_fn = verifier.decorator(
            a=(lambda x: x > 5, lambda x: x < 10),
            c=lambda x: x[:3] == 'foo',
            d=lambda x: x is not None,
            e=lambda x: x == 1
        )(sample_function)
        decorated_fn(6, 1, 'foo-asdaads', d=7)
        decorated_fn(6, 1, 'foo-asdaads', d='sss')
        decorated_fn(6, 1, 'foo-asdaads', d=0.1, e=1)

        pytest.raises(ValueError, decorated_fn, 6, None, 'foo-aaa')
        pytest.raises(ValueError, decorated_fn, 5, None, 'foo-aaa', d=5)
        pytest.raises(ValueError, decorated_fn, 10, None, 'foo-aaa', d=5)
        pytest.raises(ValueError, decorated_fn, 6, None, 'foo-aaa', d=5, e=7)


def test_verify() -> None:

    class A:
        a = 'foo'

    @verify_type(a=int, b=str, d=(int, None), e=float)
    @verify_subclass(c=A)
    @verify_value(a=(lambda x: x > 5, lambda x: x < 10), c=lambda x: x.a == 'foo', d=lambda x: x is None or x < 0)
    def foo(
        a: typing.Any, b: typing.Any, c: typing.Any, d: typing.Optional[typing.Any] = None, **kwargs: typing.Any
    ) -> None:
        pass

    foo(6, 'bar', A)
    foo(7, 'bar', A, d=-1)
    foo(6, 'bar', A, e=0.1)

    pytest.raises(TypeError, foo, 'foo', 'bar', A)
    pytest.raises(TypeError, foo, 6, 'bar', int)
    pytest.raises(ValueError, foo, 3, 'bar', A)
    A.a = 'bar'
    pytest.raises(ValueError, foo, 6, 'bar', A)
    A.a = 'foo'
    pytest.raises(ValueError, foo, 6, 'bar', A, d=1)
