import pytest

from obscura_bot.security import can_access_client, validate_service_url


def test_client_access_is_scoped_to_assignment() -> None:
    assignments = {10: [1, 2], 20: [3]}
    assert can_access_client(10, 2, assignments, admin_id=99)
    assert not can_access_client(10, 3, assignments, admin_id=99)
    assert can_access_client(99, 3, assignments, admin_id=99)


def test_remote_http_is_rejected() -> None:
    with pytest.raises(RuntimeError, match="HTTPS"):
        validate_service_url("http://panel.example.com")


def test_loopback_http_is_allowed() -> None:
    assert validate_service_url("http://127.0.0.1:2095/") == "http://127.0.0.1:2095"


def test_embedded_credentials_are_rejected() -> None:
    with pytest.raises(RuntimeError, match="embedded credentials"):
        validate_service_url("https://user:pass@panel.example.com")

