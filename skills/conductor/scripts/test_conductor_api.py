"""Offline tests for remote URL normalization and Orkes authentication."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


SCRIPT = Path(__file__).with_name("conductor_api.py")
SPEC = importlib.util.spec_from_file_location("conductor_api_fallback", SCRIPT)
assert SPEC and SPEC.loader
conductor_api = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(conductor_api)


@pytest.mark.parametrize(
    ("provided", "expected"),
    [
        ("https://developer.orkescloud.com/", "https://developer.orkescloud.com/api"),
        ("https://pg-qa.orkesconductor.com", "https://pg-qa.orkesconductor.com/api"),
        ("https://example.com/api/", "https://example.com/api"),
        ("https://example.com/custom/conductor/", "https://example.com/custom/conductor"),
    ],
)
def test_normalize_server_url(provided: str, expected: str) -> None:
    assert conductor_api.normalize_server_url(provided) == expected


def test_key_secret_are_exchanged_without_being_returned(monkeypatch) -> None:
    monkeypatch.setenv("CONDUCTOR_SERVER_URL", "https://developer.orkescloud.com/")
    monkeypatch.setenv("CONDUCTOR_AUTH_KEY", "test-key")
    monkeypatch.setenv("CONDUCTOR_AUTH_SECRET", "test-secret")
    monkeypatch.delenv("CONDUCTOR_AUTH_TOKEN", raising=False)
    seen = {}

    def fake_request(url, token, method="GET", body=None, expect_json=True):
        seen.update(url=url, token=token, method=method, body=body)
        return {"token": "exchanged-jwt"}

    monkeypatch.setattr(conductor_api, "request_json", fake_request)
    base, token = conductor_api.get_config()

    assert base == "https://developer.orkescloud.com/api"
    assert token == "exchanged-jwt"
    assert seen == {
        "url": "https://developer.orkescloud.com/api/token",
        "token": "",
        "method": "POST",
        "body": {"keyId": "test-key", "keySecret": "test-secret"},
    }


def test_explicit_token_takes_precedence(monkeypatch) -> None:
    monkeypatch.setenv("CONDUCTOR_SERVER_URL", "https://example.com/api")
    monkeypatch.setenv("CONDUCTOR_AUTH_TOKEN", "existing-token")
    monkeypatch.setenv("CONDUCTOR_AUTH_KEY", "test-key")
    monkeypatch.setenv("CONDUCTOR_AUTH_SECRET", "test-secret")

    def fail_exchange(*_args):
        raise AssertionError("key/secret exchange must not run when a token is set")

    monkeypatch.setattr(conductor_api, "exchange_auth_token", fail_exchange)
    assert conductor_api.get_config() == (
        "https://example.com/api",
        "existing-token",
    )


def test_partial_key_pair_fails(monkeypatch) -> None:
    monkeypatch.setenv("CONDUCTOR_SERVER_URL", "https://example.com/api")
    monkeypatch.setenv("CONDUCTOR_AUTH_KEY", "test-key")
    monkeypatch.delenv("CONDUCTOR_AUTH_SECRET", raising=False)
    monkeypatch.delenv("CONDUCTOR_AUTH_TOKEN", raising=False)

    with pytest.raises(SystemExit):
        conductor_api.get_config()
