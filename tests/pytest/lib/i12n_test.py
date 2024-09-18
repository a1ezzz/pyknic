
from abc import ABCMeta, abstractmethod

import pytest

from pyknic.lib.registry import APIRegistry, DuplicateAPIIdError
from pyknic.lib.i12n import register_implementation


def test() -> None:
    registry = APIRegistry()

    class Proto(metaclass=ABCMeta):

        @abstractmethod
        def foo(self) -> None:
            raise NotImplementedError('!')

    @register_implementation(registry, Proto)
    class Implementation(Proto):
        def foo(self) -> None:
            pass

    assert(registry[Proto] is Implementation)

    with pytest.raises(DuplicateAPIIdError):
        @register_implementation(registry, Proto)
        class AlternateImplementation(Proto):
            def foo(self) -> None:
                pass

    with pytest.raises(NotImplementedError):
        @register_implementation(registry, Proto)
        class NotAImplementation:
            def foo(self) -> None:
                pass
