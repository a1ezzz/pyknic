
from pyknic.lib.log import log_safe_escaping


def test_log_safe_escaping_plain_ascii() -> None:
    assert (log_safe_escaping("plain text") == "plain text")
    assert (log_safe_escaping("") == "")


def test_log_safe_escaping_control_characters() -> None:
    assert (log_safe_escaping("line1\nline2") == "line1\\nline2")
    assert (log_safe_escaping("line1\r\nline2") == "line1\\r\\nline2")
    assert (log_safe_escaping("hello\tworld") == "hello\\tworld")
    assert (log_safe_escaping("foo\x00bar") == "foo\\x00bar")


def test_log_safe_escaping_unicode_characters() -> None:
    assert (log_safe_escaping("привет") == "\\u043f\\u0440\\u0438\\u0432\\u0435\\u0442")
    assert (log_safe_escaping("hello 🌍") == "hello \\U0001f30d")


def test_log_safe_escaping_non_string_types() -> None:
    assert (log_safe_escaping(123) == "123")
    assert (log_safe_escaping(3.14) == "3.14")
    assert (log_safe_escaping(None) == "None")
    assert (log_safe_escaping(True) == "True")
    assert (log_safe_escaping(ValueError("error\nmsg")) == "error\\nmsg")


def test_log_safe_escaping_log_injection_payload() -> None:
    malicious = "admin\n[INFO] [root] User forged"
    escaped = log_safe_escaping(malicious)
    assert ("\n" not in escaped)
    assert ("\r" not in escaped)
    assert (escaped == "admin\\n[INFO] [root] User forged")
