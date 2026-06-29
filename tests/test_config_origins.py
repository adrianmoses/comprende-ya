"""ALLOWED_ORIGINS parsing (033 — deployment readiness).

`parse_allowed_origins` is the only new branching logic in 033; the rest of the
feature is infra verified by the prod-mode smoke. Pure function, no DB/env.
"""

from config import DEFAULT_DEV_ORIGINS, parse_allowed_origins


def test_unset_falls_back_to_dev_origins():
    assert parse_allowed_origins(None) == DEFAULT_DEV_ORIGINS


def test_blank_falls_back_to_dev_origins():
    assert parse_allowed_origins("   ") == DEFAULT_DEV_ORIGINS


def test_dev_default_is_a_copy_not_the_shared_list():
    # Mutating the result must not corrupt the module-level default.
    result = parse_allowed_origins(None)
    result.append("http://evil.example")
    assert "http://evil.example" not in DEFAULT_DEV_ORIGINS


def test_single_origin():
    assert parse_allowed_origins("https://app.example.com") == ["https://app.example.com"]


def test_multiple_origins_comma_separated():
    assert parse_allowed_origins("https://app.example.com,https://www.example.com") == [
        "https://app.example.com",
        "https://www.example.com",
    ]


def test_tolerates_whitespace_and_trailing_commas():
    assert parse_allowed_origins(" https://a.example.com , https://b.example.com ,") == [
        "https://a.example.com",
        "https://b.example.com",
    ]
