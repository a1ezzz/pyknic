
import pytest

from pyknic.lib.registry import WNoSuchAPIIdError, WDuplicateAPIIdError, WAPIRegistryProto, WAPIRegistry, register_api


def test_exceptions():
    assert(issubclass(WNoSuchAPIIdError, Exception) is True)
    assert(issubclass(WDuplicateAPIIdError, Exception) is True)


def test_abstract():
    pytest.raises(TypeError, WAPIRegistryProto)
    pytest.raises(NotImplementedError, WAPIRegistryProto.register, None, None, None)
    pytest.raises(NotImplementedError, WAPIRegistryProto.unregister, None, None)
    pytest.raises(NotImplementedError, WAPIRegistryProto.get, None, None)
    pytest.raises(NotImplementedError, WAPIRegistryProto.ids, None)
    pytest.raises(NotImplementedError, WAPIRegistryProto.has, None, None)


class TestWAPIRegistry:

    def test(self):
        registry = WAPIRegistry()
        pytest.raises(WNoSuchAPIIdError, registry.get, 'foo')
        pytest.raises(WNoSuchAPIIdError, registry.get, 'bar')

        registry.register('foo', 1)
        assert(registry.get('foo') == 1)
        pytest.raises(WNoSuchAPIIdError, registry.get, 'bar')

        assert(registry.has('foo') is True)
        assert('foo' in registry)

        assert(registry.has('bar') is False)
        assert('bar' not in registry)

        pytest.raises(WDuplicateAPIIdError, registry.register, 'foo', 1)

        registry.register('bar', 1)
        assert(registry['foo'] == 1)
        assert(registry['bar'] == 1)

        assert(registry.has('foo') is True)
        assert('foo' in registry)

        assert(registry.has('bar') is True)
        assert('bar' in registry)

        secondary_registry = WAPIRegistry(fallback_registry=registry)
        assert(secondary_registry['foo'] == 1)
        assert(secondary_registry['bar'] == 1)
        pytest.raises(WNoSuchAPIIdError, secondary_registry.get, 'zzz')
        pytest.raises(WNoSuchAPIIdError, secondary_registry.get, 'xxx')

        registry.register('zzz', 1)
        assert(secondary_registry['foo'] == 1)
        assert(secondary_registry['bar'] == 1)
        assert(secondary_registry['zzz'] == 1)
        pytest.raises(WNoSuchAPIIdError, secondary_registry.get, 'xxx')

        secondary_registry.register('xxx', 1)
        assert(secondary_registry['foo'] == 1)
        assert(secondary_registry['bar'] == 1)
        assert(secondary_registry['zzz'] == 1)
        assert(secondary_registry['xxx'] == 1)
        pytest.raises(WNoSuchAPIIdError, registry.get, 'xxx')

        secondary_registry.register('zzz', 2)
        assert(secondary_registry['foo'] == 1)
        assert(secondary_registry['bar'] == 1)
        assert(secondary_registry['zzz'] == 2)
        assert(secondary_registry['xxx'] == 1)
        pytest.raises(WNoSuchAPIIdError, registry.get, 'xxx')

        registry.unregister('zzz')
        assert(secondary_registry['foo'] == 1)
        assert(secondary_registry['bar'] == 1)
        assert(secondary_registry['xxx'] == 1)
        pytest.raises(WNoSuchAPIIdError, registry.get, 'xxx')
        pytest.raises(WNoSuchAPIIdError, registry.get, 'zzz')

        pytest.raises(WNoSuchAPIIdError, registry.unregister, 'zzz')

        registry_ids_gen = tuple(registry.ids())
        assert(len(registry_ids_gen) == 2)
        assert('foo' in registry_ids_gen)
        assert('bar' in registry_ids_gen)

        secondary_registry_ids_gen = tuple(secondary_registry.ids())
        assert(len(secondary_registry_ids_gen) == 2)
        assert('xxx' in secondary_registry_ids_gen)
        assert('zzz' in secondary_registry_ids_gen)


def test_register_api():

    def foo(a, b):
        return a + b

    def bar(a, b):
        return a - b

    registry = WAPIRegistry()

    decorated_foo = register_api(registry)(foo)
    decorated_bar = register_api(registry, api_id='zzz')(bar)

    assert(decorated_foo(3, 4) == 7)
    assert(decorated_bar(3, 4) == -1)

    assert(registry['test_register_api.<locals>.foo'](5, 2) == 7)
    assert(registry['zzz'](5, 2) == 3)

    pytest.raises(WNoSuchAPIIdError, registry.get, 'bar')
    class C:
        api_id = 'bar'

    register_api(registry, api_id=lambda x: x.api_id, callable_api_id=True)(C)
    assert(registry['bar'] is C)

    with pytest.raises(ValueError):
        class D:
            pass
        register_api(registry, api_id=1, callable_api_id=True)(D)
