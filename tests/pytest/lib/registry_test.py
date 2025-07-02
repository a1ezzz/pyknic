# -*- coding: utf-8 -*-

import itertools

import pytest

from pyknic.lib.registry import NoSuchAPIIdError, DuplicateAPIIdError, APIRegistryProto, APIRegistry, register_api
from pyknic.lib.registry import hash_id_by_tokens


def test_exceptions() -> None:
    assert(issubclass(NoSuchAPIIdError, Exception) is True)
    assert(issubclass(DuplicateAPIIdError, Exception) is True)


def test_abstract() -> None:
    pytest.raises(TypeError, APIRegistryProto)
    pytest.raises(NotImplementedError, APIRegistryProto.register, None, None, None)
    pytest.raises(NotImplementedError, APIRegistryProto.unregister, None, None)
    pytest.raises(NotImplementedError, APIRegistryProto.get, None, None)
    pytest.raises(NotImplementedError, APIRegistryProto.ids, None)
    pytest.raises(NotImplementedError, APIRegistryProto.has, None, None)
    pytest.raises(NotImplementedError, APIRegistryProto.__iter__, None)


class TestAPIRegistry:

    def test(self) -> None:
        registry = APIRegistry()
        pytest.raises(NoSuchAPIIdError, registry.get, 'foo')
        pytest.raises(NoSuchAPIIdError, registry.get, 'bar')

        registry.register('foo', 1)
        assert(registry.get('foo') == 1)
        pytest.raises(NoSuchAPIIdError, registry.get, 'bar')

        assert(registry.has('foo') is True)
        assert('foo' in registry)

        assert(registry.has('bar') is False)
        assert('bar' not in registry)

        pytest.raises(DuplicateAPIIdError, registry.register, 'foo', 1)

        registry.register('bar', 1)
        assert(registry['foo'] == 1)
        assert(registry['bar'] == 1)

        assert(registry.has('foo') is True)
        assert('foo' in registry)

        assert(registry.has('bar') is True)
        assert('bar' in registry)

        secondary_registry = APIRegistry(fallback_registry=registry)
        assert(secondary_registry['foo'] == 1)
        assert(secondary_registry['bar'] == 1)
        pytest.raises(NoSuchAPIIdError, secondary_registry.get, 'zzz')
        pytest.raises(NoSuchAPIIdError, secondary_registry.get, 'xxx')

        registry.register('zzz', 1)
        assert(secondary_registry['foo'] == 1)
        assert(secondary_registry['bar'] == 1)
        assert(secondary_registry['zzz'] == 1)
        pytest.raises(NoSuchAPIIdError, secondary_registry.get, 'xxx')

        secondary_registry.register('xxx', 1)
        assert(secondary_registry['foo'] == 1)
        assert(secondary_registry['bar'] == 1)
        assert(secondary_registry['zzz'] == 1)
        assert(secondary_registry['xxx'] == 1)
        pytest.raises(NoSuchAPIIdError, registry.get, 'xxx')

        secondary_registry.register('zzz', 2)
        assert(secondary_registry['foo'] == 1)
        assert(secondary_registry['bar'] == 1)
        assert(secondary_registry['zzz'] == 2)
        assert(secondary_registry['xxx'] == 1)
        pytest.raises(NoSuchAPIIdError, registry.get, 'xxx')

        registry.unregister('zzz')
        assert(secondary_registry['foo'] == 1)
        assert(secondary_registry['bar'] == 1)
        assert(secondary_registry['xxx'] == 1)
        pytest.raises(NoSuchAPIIdError, registry.get, 'xxx')
        pytest.raises(NoSuchAPIIdError, registry.get, 'zzz')

        pytest.raises(NoSuchAPIIdError, registry.unregister, 'zzz')

        registry_ids_gen = tuple(registry.ids())
        assert(len(registry_ids_gen) == 2)
        assert('foo' in registry_ids_gen)
        assert('bar' in registry_ids_gen)

        secondary_registry_ids_gen = tuple(secondary_registry.ids())
        assert(len(secondary_registry_ids_gen) == 2)
        assert('xxx' in secondary_registry_ids_gen)
        assert('zzz' in secondary_registry_ids_gen)

    def test_iter(self) -> None:
        registry = APIRegistry()

        assert(list(registry) == [])

        registry.register('foo', 1)
        registry.register('bar', 2)
        registry.register('xxx', 3)

        assert(set(registry) == {('foo', 1), ('bar', 2), ('xxx', 3)})


def test_register_api() -> None:

    def foo(a: int, b: int) -> int:
        return a + b

    def bar(a: int, b: int) -> int:
        return a - b

    registry = APIRegistry()

    decorated_foo = register_api(registry)(foo)
    decorated_bar = register_api(registry, api_id='zzz')(bar)

    assert(decorated_foo(3, 4) == 7)
    assert(decorated_bar(3, 4) == -1)

    assert(registry['test_register_api.<locals>.foo'](5, 2) == 7)
    assert(registry['zzz'](5, 2) == 3)

    pytest.raises(NoSuchAPIIdError, registry.get, 'bar')

    class C:
        api_id = 'bar'

    register_api(registry, api_id=lambda x: x.api_id, callable_api_id=True)(C)
    assert(registry['bar'] is C)

    with pytest.raises(ValueError):
        class D:
            pass
        register_api(registry, api_id=1, callable_api_id=True)(D)


def test_hash_id_by_tokens():
    unsorted_hashes = [
        hash_id_by_tokens('single_token'),
        hash_id_by_tokens('first_token'),
        hash_id_by_tokens('first_token', 'second_token'),
        hash_id_by_tokens('order1', 'order2'),
        hash_id_by_tokens('order2', 'order1'),
        hash_id_by_tokens('order1', 'order2', 'order3'),
    ]

    for hash_a, hash_b in itertools.permutations(unsorted_hashes, 2):
        assert(hash_a != hash_b)

    unsorted_hashes = [
        hash_id_by_tokens('single_token', pre_sort=False),
        hash_id_by_tokens('first_token', pre_sort=False),
        hash_id_by_tokens('first_token', 'second_token', pre_sort=False),
        hash_id_by_tokens('order1', 'order2', pre_sort=False),
        hash_id_by_tokens('order2', 'order1', pre_sort=False),
        hash_id_by_tokens('order1', 'order2', 'order3', pre_sort=False),
    ]

    for hash_a, hash_b in itertools.permutations(unsorted_hashes, 2):
        assert(hash_a != hash_b)

    sorted_hashes = [
        hash_id_by_tokens('single_token', pre_sort=True),
        hash_id_by_tokens('first_token', pre_sort=True),
        hash_id_by_tokens('first_token', 'second_token', pre_sort=True),
        hash_id_by_tokens('order1', 'order2', pre_sort=True),
        hash_id_by_tokens('order1', 'order2', 'order3', pre_sort=True),
    ]

    for hash_a, hash_b in itertools.permutations(sorted_hashes, 2):
        assert(hash_a != hash_b)

    assert(hash_id_by_tokens('order1', 'order2', pre_sort=True) == hash_id_by_tokens('order2', 'order1', pre_sort=True))
