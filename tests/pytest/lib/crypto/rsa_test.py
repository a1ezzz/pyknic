# -*- coding: utf-8 -*-

import pytest

from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization

from pyknic.lib.crypto.rsa import RSAPrivateKey, RSAPublicKey, InvalidSignature


class TestRSAPrivateKey:

    def test_sign(self) -> None:
        rsa_key = RSAPrivateKey.generate(1024)
        message = b'Test data'
        signature = rsa_key.sign(message, 'sha256')

        pub_key = rsa_key.public_key()
        assert(isinstance(pub_key, RSAPublicKey))
        pub_key.verify(signature, message, 'sha256')

        invalid_signature = b'0' * (len(signature))
        with pytest.raises(InvalidSignature):
            pub_key.verify(invalid_signature, message, 'sha256')

    def test_import_export_pem(self) -> None:
        rsa_key1 = RSAPrivateKey.generate(1024)
        rsa_key2 = RSAPrivateKey.generate(1024)
        message = b'Test data'

        signature = rsa_key1.sign(message, 'sha256')
        rsa_key1.public_key().verify(signature, message, 'sha256')

        with pytest.raises(InvalidSignature):
            rsa_key2.public_key().verify(signature, message, 'sha256')

        imported_rsa_key1 = RSAPrivateKey.import_pem(rsa_key1.export_pem())
        imported_rsa_key2 = RSAPrivateKey.import_pem(rsa_key2.export_pem())
        assert(isinstance(imported_rsa_key1, RSAPrivateKey))
        assert(isinstance(imported_rsa_key2, RSAPrivateKey))

        imported_rsa_key1.public_key().verify(signature, message, 'sha256')

        with pytest.raises(InvalidSignature):
            imported_rsa_key2.public_key().verify(signature, message, 'sha256')

    def test_encrypted_import_export_pem(self) -> None:
        message = b'Test data'

        rsa_key1 = RSAPrivateKey.generate(1024)
        key_password = b'secret key'
        imported_rsa_key1 = RSAPrivateKey.import_pem(rsa_key1.export_pem(key_password), key_password)

        # everything is ok
        imported_rsa_key1.public_key().verify(
            rsa_key1.sign(message, 'sha256'),
            message,
            'sha256'
        )

    def test_read_encrypted_pem(self) -> None:
        rsa_key1 = RSAPrivateKey.generate(1024)
        key_password = b'secret key'

        with pytest.raises(ValueError):
            _ = RSAPrivateKey.import_pem(rsa_key1.export_pem(key_password))

    def test_unencrypt_unencrypted_pem(self) -> None:
        rsa_key1 = RSAPrivateKey.generate(1024)
        key_password = b'secret key'

        with pytest.raises(ValueError):
            _ = RSAPrivateKey.import_pem(rsa_key1.export_pem(), key_password)

    def test_unencrypt_w_invalid_password_pem(self) -> None:
        rsa_key1 = RSAPrivateKey.generate(1024)
        key_password = b'secret key'
        invalid_key_password = b'qazwsx'

        with pytest.raises(ValueError):
            _ = RSAPrivateKey.import_pem(rsa_key1.export_pem(key_password), invalid_key_password)

    def test_non_rsa_import_pem(self) -> None:
        ec_key = ec.generate_private_key(ec.SECP384R1())
        ec_pem = ec_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )

        with pytest.raises(ValueError):
            RSAPrivateKey.import_pem(ec_pem)


class TestRSAPublicKey:

    def test_import_export_pem(self) -> None:
        rsa_key1 = RSAPrivateKey.generate(1024)
        pub_key1 = rsa_key1.public_key()
        rsa_key2 = RSAPrivateKey.generate(1024)
        pub_key2 = rsa_key2.public_key()
        message = b'Test data'

        signature = rsa_key1.sign(message, 'sha256')
        pub_key1.verify(signature, message, 'sha256')

        with pytest.raises(InvalidSignature):
            pub_key2.verify(signature, message, 'sha256')

        imported_pub_key1 = RSAPublicKey.import_pem(pub_key1.export_pem())
        imported_pub_key2 = RSAPublicKey.import_pem(pub_key2.export_pem())
        assert(isinstance(imported_pub_key1, RSAPublicKey))
        assert(isinstance(imported_pub_key2, RSAPublicKey))

        imported_pub_key1.verify(signature, message, 'sha256')

        with pytest.raises(InvalidSignature):
            imported_pub_key2.verify(signature, message, 'sha256')

    def test_non_rsa_import_pem(self) -> None:
        ec_key = ec.generate_private_key(ec.SECP384R1())
        ec_pub_key = ec_key.public_key()
        ec_pem = ec_pub_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )

        with pytest.raises(ValueError):
            RSAPublicKey.import_pem(ec_pem)
