
import base64
import enum
import json
import os
import typing


@enum.unique
class TestSecrets(enum.Enum):
    __test__ = False  # pytest issue

    s3_test_uri = 's3_test_uri'


def decode_pytest_secret(key: typing.Union[str | TestSecrets]) -> typing.Any:

    if isinstance(key, TestSecrets):
        key = key.value

    if 'PYTEST_EXTRA_SECRETS' in os.environ:
        decoded_b64_msg = base64.b64decode(os.environ['PYTEST_EXTRA_SECRETS'])
        secrets = json.loads(decoded_b64_msg.decode())

        if not isinstance(secrets, dict):
            raise RuntimeError(f'Invalid secretu structure -- {secrets.__class__} (dict expected)!')

        return secrets.get(key, None)
    return None
