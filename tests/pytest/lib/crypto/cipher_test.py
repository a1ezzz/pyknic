# -*- coding: utf-8 -*-

import pytest
import typing

import pydantic

from pyknic.lib.crypto.proto import CipherProto
from pyknic.lib.crypto.cipher import CipherModeModel, CBCMode, CTRMode, AES128CBCCipher, AES192CBCCipher
from pyknic.lib.crypto.cipher import AES256CBCCipher, AES128CTRCipher, AES192CTRCipher, AES256CTRCipher
from pyknic.lib.crypto.random import random_bytes


class TestCipherModeModel:

    def test(self) -> None:

        model = CipherModeModel()  # this is ok since it is not inherited from the ABCMeta
        assert(isinstance(model, CipherModeModel))
        assert(isinstance(model, pydantic.BaseModel))

        pytest.raises(NotImplementedError, CipherModeModel.generate, None)
        pytest.raises(NotImplementedError, CipherModeModel.deserialize, None, None)
        pytest.raises(NotImplementedError, model.c10y_mode)


class TestCBCMode:

    def test_plain(self) -> None:
        model = CBCMode(initialization_vector=b'aaa')
        assert(isinstance(model, CipherModeModel))
        assert(isinstance(model, pydantic.BaseModel))
        assert(model.c10y_mode() is not None)

    def test(self) -> None:
        cipher = AES128CBCCipher(b'b' * int(128 / 8))  # type: ignore[abstract]
        model1 = CBCMode.generate(cipher)
        assert(model1.c10y_mode() is not None)

        model2 = CBCMode.generate(cipher)
        assert(model2.initialization_vector != model1.initialization_vector)

        model2 = CBCMode.deserialize(model1.model_dump(), cipher)
        assert(isinstance(model2, CBCMode))
        assert(model2.initialization_vector == model1.initialization_vector)

    def test_exceptions(self) -> None:
        cipher = AES128CBCCipher(b'b' * int(128 / 8))  # type: ignore[abstract]

        corrupted_model = CBCMode(initialization_vector=b'aaa')
        pytest.raises(ValueError, CBCMode.deserialize, corrupted_model.model_dump(), cipher)


class TestCTRMode:

    def test_plain(self) -> None:
        model = CTRMode(nonce=(b'a' * 128))
        assert(isinstance(model, CipherModeModel))
        assert(isinstance(model, pydantic.BaseModel))
        assert(model.c10y_mode() is not None)

    def test(self) -> None:
        cipher = AES128CBCCipher(b'b' * int(128 / 8))  # type: ignore[abstract]
        model1 = CTRMode.generate(cipher)
        assert(model1.c10y_mode() is not None)

        model2 = CTRMode.generate(cipher)
        assert(model2.nonce != model1.nonce)

        model2 = CTRMode.deserialize(model1.model_dump(), cipher)
        assert(isinstance(model2, CTRMode))
        assert(model2.nonce == model1.nonce)

    def test_exceptions(self) -> None:
        cipher = AES128CBCCipher(b'b' * int(128 / 8))  # type: ignore[abstract]

        with pytest.raises(ValueError):
            _ = CTRMode(nonce=b'a')  # too short

        corrupted_model = CTRMode(nonce=(b'a' * 128))
        pytest.raises(ValueError, CTRMode.deserialize, corrupted_model.model_dump(), cipher)


@pytest.mark.parametrize(
    'cipher_cls',
    [
        AES128CBCCipher,
        AES192CBCCipher,
        AES256CBCCipher,
        AES128CTRCipher,
        AES192CTRCipher,
        AES256CTRCipher
    ]
)
class TestAESCipher:

    def test(self, cipher_cls: typing.Type[CipherProto]) -> None:
        key_size = cipher_cls.key_size()
        assert(key_size is not None)

        cipher_key1 = random_bytes(key_size)
        cipher_key2 = random_bytes(key_size)

        cipher_encryptor1 = cipher_cls.create_encryptor(cipher_key1)
        cipher_encryptor2 = cipher_cls.create_encryptor(cipher_key2)

        cipher_decryptor1 = cipher_cls.create_decryptor(cipher_key1, cipher_encryptor1.decryptor_init_data())
        cipher_decryptor2 = cipher_cls.create_decryptor(cipher_key2, cipher_encryptor2.decryptor_init_data())

        secret_text = b'some secret text'
        encrypted_text1 = b''.join(cipher_encryptor1.encrypt([secret_text]))  # type: ignore[arg-type]
        encrypted_text2 = b''.join(cipher_encryptor2.encrypt([secret_text]))  # type: ignore[arg-type]

        assert(encrypted_text1 != encrypted_text2)
        assert(b''.join(cipher_decryptor1.decrypt([encrypted_text1])) == secret_text)  # type: ignore[arg-type]
        assert(b''.join(cipher_decryptor2.decrypt([encrypted_text2])) == secret_text)  # type: ignore[arg-type]

        assert(b''.join(cipher_decryptor1.decrypt([encrypted_text2])) != secret_text)  # type: ignore[arg-type]
        assert(b''.join(cipher_decryptor2.decrypt([encrypted_text1])) != secret_text)  # type: ignore[arg-type]

    def test_exceptions(self, cipher_cls: typing.Type[CipherProto]) -> None:
        key_size = cipher_cls.key_size()
        assert(key_size is not None)

        cipher_key = random_bytes(key_size)
        cipher_encryptor = cipher_cls.create_encryptor(cipher_key)
        cipher_decryptor = cipher_cls.create_decryptor(cipher_key, cipher_encryptor.decryptor_init_data())

        secret_text = b'some secret text'
        encrypted_text = b''.join(cipher_encryptor.encrypt([secret_text]))  # type: ignore[arg-type]

        with pytest.raises(RuntimeError):
            _ = list(cipher_encryptor.decrypt([encrypted_text]))  # type: ignore[arg-type]

        with pytest.raises(RuntimeError):
            _ = list(cipher_decryptor.encrypt([secret_text]))  # type: ignore[arg-type]

        with pytest.raises(ValueError):
            cipher_cls.create_encryptor(b'small key')

        with pytest.raises(ValueError):
            cipher_cls.create_decryptor(b'small key', cipher_encryptor.decryptor_init_data())
