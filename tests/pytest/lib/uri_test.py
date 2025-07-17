# -*- coding: utf-8 -*-

import pytest

from pyknic.lib.uri import URI, URIQuery, URIQueryInvalidSingleParameter


def test_exceptions() -> None:
    assert(issubclass(URIQueryInvalidSingleParameter, Exception) is True)


class TestURI:

    def test(self) -> None:
        uri = URI()

        assert(uri.scheme is None)
        assert(uri.username is None)
        assert(uri.password is None)
        assert(uri.hostname is None)
        assert(uri.port is None)
        assert(uri.path is None)
        assert(uri.query is None)
        assert(uri.fragment is None)
        assert(str(uri) == '')

    def test_args1(self) -> None:
        uri = URI(scheme='proto', hostname='host1', path='/foo')

        assert(uri.scheme == 'proto')
        assert(uri.username is None)
        assert(uri.password is None)
        assert(uri.hostname == 'host1')
        assert(uri.port is None)
        assert(uri.path == 'foo')
        assert(uri.query is None)
        assert(uri.fragment is None)
        assert(str(uri) == 'proto://host1/foo')

    def test_args2(self) -> None:
        uri = URI(
            scheme='proto', username='local_user', password='secret', hostname='host1', port=40,
            path='foo', query='q=10;p=2', fragment='section1'
        )

        assert(uri.scheme == 'proto')
        assert(uri.username == 'local_user')
        assert(uri.password == 'secret')
        assert(uri.hostname == 'host1')
        assert(uri.port == 40)
        assert(uri.path == 'foo')
        assert(uri.query == 'q=10;p=2')
        assert(uri.fragment == 'section1')
        assert(str(uri) == 'proto://local_user:secret@host1:40/foo?q=10;p=2#section1')

    def test_args_and_reset(self) -> None:
        uri = URI(scheme='proto', path='/foo')
        assert(str(uri) == 'proto:///foo')

        uri.path = None
        assert(str(uri) == 'proto://')

        uri.scheme = None
        assert (str(uri) == '')

    def test_parse1(self) -> None:
        uri = URI.parse('')
        assert(uri.scheme is None)
        assert(uri.username is None)
        assert(uri.password is None)
        assert(uri.hostname is None)
        assert(uri.port is None)
        assert(uri.path is None)
        assert(uri.query is None)
        assert(uri.fragment is None)

    def test_parse2(self) -> None:
        uri = URI.parse('proto://hostname/foo/bar')
        assert(uri.scheme == 'proto')
        assert(uri.username is None)
        assert(uri.password is None)
        assert(uri.hostname == 'hostname')
        assert(uri.port is None)
        assert(uri.path == 'foo/bar')
        assert(uri.query is None)
        assert(uri.fragment is None)

    def test_parse3(self) -> None:
        uri = URI.parse('proto://user:pass@hostname:90#foo-bar')
        assert(uri.scheme == 'proto')
        assert(uri.username == 'user')
        assert(uri.password == 'pass')
        assert(uri.hostname == 'hostname')
        assert(uri.port == 90)
        assert(uri.path is None)
        assert(uri.query is None)
        assert(uri.fragment == 'foo-bar')

    def test_parse4(self) -> None:
        uri = URI.parse('/foo/bar?path=q')
        assert(uri.scheme is None)
        assert(uri.username is None)
        assert(uri.password is None)
        assert(uri.hostname is None)
        assert(uri.port is None)
        assert(uri.path == 'foo/bar')
        assert(uri.query == 'path=q')
        assert(uri.fragment is None)

    def test_parse5(self) -> None:
        uri = URI.parse('/foo/bar')
        assert(uri.scheme is None)
        assert(uri.username is None)
        assert(uri.password is None)
        assert(uri.hostname is None)
        assert(uri.port is None)
        assert(uri.path == 'foo/bar')
        assert(uri.query is None)
        assert(uri.fragment is None)


class TestURIQuery:

    def test(self) -> None:
        query = URIQuery()
        assert(str(query) == '')
        assert(list(query) == [])

        assert('foo' not in query)

    def test_parse(self) -> None:
        query = URIQuery.parse('foo=&bar=zzz&foo=bar&bar=1')
        assert(str(query) == 'bar=zzz&bar=1&foo=&foo=bar')
        assert(list(query) == ['bar', 'foo'])

        assert('foo' in query)
        assert('xxx' not in query)

        assert(str(URIQuery.parse('')) == '')

    def test_update(self) -> None:
        query = URIQuery.parse('foo=&bar=zzz&foo=bar&bar=1')
        query.update('foo', '2')
        query.update('bar', ('3', 'xxx'), append=True)

        assert(str(query) == 'bar=zzz&bar=1&bar=3&bar=xxx&foo=2')
        assert(list(query) == ['bar', 'foo'])

        query.remove('bar')
        assert(str(query) == 'foo=2')

    def test_getitem(self) -> None:
        query = URIQuery.parse('foo=&bar=zzz&foo=bar&bar=1')
        assert(query['foo'] == ('', 'bar'))
        assert(query['bar'] == ('zzz', '1'))

    def test_parameters(self) -> None:
        query = URIQuery.parse('foo=&bar=zzz&foo=bar&bar=1')
        parameters_set = set(query.parameters())
        assert(parameters_set == {('foo', ('', 'bar')), ('bar', ('zzz', '1'))})

    def test_single_parameters(self) -> None:
        query = URIQuery.parse('foo=&bar=zzz&foo=bar&bar=1&xxx=20&f_value=2.1&n_value=')

        with pytest.raises(URIQueryInvalidSingleParameter):
            query.single_parameter('yyy', int)

        with pytest.raises(URIQueryInvalidSingleParameter):
            query.single_parameter('foo', int)

        with pytest.raises(URIQueryInvalidSingleParameter):
            query.single_parameter('n_value', int)

        assert(query.single_parameter('xxx', int) == 20)
        assert(query.single_parameter('f_value', float) == 2.1)
