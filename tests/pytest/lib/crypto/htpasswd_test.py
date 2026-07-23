# -*- coding: utf-8 -*-

import pathlib
import typing

import pytest

from pyknic.lib.crypto.htpasswd import HTPasswdHashCheckerProto, HTPasswdBCrypt, HTPasswdArgon2, HTPasswdEntry, HTPasswd


def test_abstract() -> None:
    pytest.raises(TypeError, HTPasswdHashCheckerProto)
    pytest.raises(NotImplementedError, HTPasswdHashCheckerProto.match, None, '', '', '')  # type: ignore[call-overload]


@pytest.mark.parametrize('checker_cls, password, hash_method, password_hash, result', [
    [HTPasswdBCrypt, 'aaa', '2a', '10$XRq.zJLdR1.A9hpNcV4k6u537cXiDIkUIxwzr6kmkFeZJtZQWSM22', True],
    [HTPasswdBCrypt, 'ccc', '2b', '10$IabiI53g3O32PvVH3KU.a.rKzRr4a1GRx4.c0XmID/mxAgzzAeZ6K', True],
    [HTPasswdBCrypt, 'bar', '2y', '05$Z7/3diNsWaUZ1JtEqQRdu.78F86tPEzPn/nEBTSVVyIugQtkAyRVK', True],
    [HTPasswdBCrypt, 'ccc', '2a', '10$XRq.zJLdR1.A9hpNcV4k6u537cXiDIkUIxwzr6kmkFeZJtZQWSM22', False],
    [HTPasswdBCrypt, 'bar', '2b', '10$IabiI53g3O32PvVH3KU.a.rKzRr4a1GRx4.c0XmID/mxAgzzAeZ6K', False],
    [HTPasswdBCrypt, 'aaa', '2y', '05$Z7/3diNsWaUZ1JtEqQRdu.78F86tPEzPn/nEBTSVVyIugQtkAyRVK', False],

    [
        HTPasswdArgon2,
        'bar',
        'argon2id',
        'v=19$m=65536,t=3,p=4$7yHxiwaO5x8r7p5RvaS9jg$wNwj6zV8Uf3uNx0pyKbOssdvdPCUqcoVrdN+Xf6JiRw',
        True
    ],
    [
        HTPasswdArgon2,
        'aaa',
        'argon2id',
        'v=19$m=65536,t=3,p=4$7yHxiwaO5x8r7p5RvaS9jg$wNwj6zV8Uf3uNx0pyKbOssdvdPCUqcoVrdN+Xf6JiRw',
        False
    ]],
    ids=[
        'bcrypt-2a-True',
        'bcrypt-2b-True',
        'bcrypt-2y-True',
        'bcrypt-2a-False',
        'bcrypt-2b-False',
        'bcrypt-2y-False',
        'argon2id-True',
        'argon2id-False',
    ]
)
def test_checkers(
    checker_cls: typing.Type[HTPasswdHashCheckerProto],
    password: str,
    hash_method: str,
    password_hash: str,
    result: bool
) -> None:
    checker = checker_cls()
    assert(isinstance(checker, HTPasswdHashCheckerProto) is True)

    assert(checker.match(password, hash_method, password_hash) == result)


@pytest.mark.parametrize('checker_cls', [HTPasswdBCrypt, HTPasswdArgon2])
def test_invalid_hash_method(checker_cls: typing.Type[HTPasswdHashCheckerProto]) -> None:
    checker = checker_cls()

    with pytest.raises(ValueError):
        checker.match('pass', 'crazy-method', 'secret-hash')


class TestHTPasswdEntry:

    @pytest.mark.parametrize('entry_str, username, password', [
        [
            'foo:$2y$05$Z7/3diNsWaUZ1JtEqQRdu.78F86tPEzPn/nEBTSVVyIugQtkAyRVK',
            'foo',
            'bar',
        ],
        [
            'aaa:$argon2id$v=19$m=65536,t=3,p=4$7yHxiwaO5x8r7p5RvaS9jg$wNwj6zV8Uf3uNx0pyKbOssdvdPCUqcoVrdN+Xf6JiRw',
            'aaa',
            'bar'
        ]
        ],
        ids=[
            'bcrypt',
            'argon2'
        ]
    )
    def test(self, entry_str: str, username: str, password: str) -> None:
        parsed_entry = HTPasswdEntry.parse(entry_str)

        assert(parsed_entry.user_name() == username)
        assert(parsed_entry.match(password) is True)
        assert(parsed_entry.match('invalid-secret') is False)
        assert(str(parsed_entry) == entry_str)

        with pytest.raises(ValueError):
            HTPasswdEntry.parse('invalid-hash-string')

        with pytest.raises(ValueError):
            HTPasswdEntry.parse('user:$unknown-method$some-hash')


class TestHTPasswd:

    def test(self, tmp_path: pathlib.Path) -> None:
        htpasswd_path = tmp_path / "htpasswd"
        with htpasswd_path.open('w') as f:
            f.write(
                """
                foo:$2y$05$Z7/3diNsWaUZ1JtEqQRdu.78F86tPEzPn/nEBTSVVyIugQtkAyRVK
                aaa:$argon2id$v=19$m=65536,t=3,p=4$7yHxiwaO5x8r7p5RvaS9jg$wNwj6zV8Uf3uNx0pyKbOssdvdPCUqcoVrdN+Xf6JiRw
                """
            )

        htpasswd = HTPasswd.read_file(str(htpasswd_path))

        assert(htpasswd.match('foo', '') is False)
        assert(htpasswd.match('foo', 'bar') is True)
        assert(htpasswd.match('unknown-user', 'bar') is False)

        assert(htpasswd.match('aaa', '') is False)
        assert(htpasswd.match('aaa', 'bar') is True)
