import pytest

from sui_bot.security import can_access_client, is_public_callback, validate_service_url


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


@pytest.mark.parametrize(
    "url",
    [
        "https://panel.example.com?token=secret",
        "https://panel.example.com/#fragment",
        " https://panel.example.com",
        "https://panel.example.com:99999",
    ],
)
def test_service_url_rejects_ambiguous_or_invalid_values(url: str) -> None:
    with pytest.raises(RuntimeError):
        validate_service_url(url)


def test_callback_authorization_is_deny_by_default() -> None:
    assert is_public_callback("language_settings")
    assert is_public_callback("select_sub_42")
    assert is_public_callback("renew_choose_42_3")
    assert not is_public_callback("manage_links")
    assert not is_public_callback("all_clients_page_1")
    assert not is_public_callback("renew_appr_requestid")
    assert not is_public_callback("unknown_future_admin_action")
