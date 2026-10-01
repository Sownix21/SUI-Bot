import pytest

from sui_bot.sui_metadata import (
    build_subscription_base_from_settings,
    build_subscription_urls,
    build_web_panel_url,
    extract_load_metadata,
    extract_partial_metadata,
)


def test_load_metadata_preserves_subscription_port_and_path():
    payload = {
        "success": True,
        "obj": {
            "subURI": "https://subscription.example.com:2096/example-secret-segment/subscription-root/",
            "inbounds": [{"id": 1, "tag": "main"}, {"tag": "invalid"}],
        },
    }

    sub_uri, inbounds = extract_load_metadata(payload)
    main, json_url, clash_url = build_subscription_urls(sub_uri, "test user")

    assert sub_uri == "https://subscription.example.com:2096/example-secret-segment/subscription-root"
    assert inbounds == [{"id": 1, "tag": "main"}]
    assert main == f"{sub_uri}/test%20user/"
    assert json_url == f"{main}?format=json"
    assert clash_url == f"{main}?format=clash"


def test_portless_panel_uri_is_used_without_rewriting():
    base = "https://subscription.example.com/token-part/nested"

    main, json_url, clash_url = build_subscription_urls(base, "test user")

    assert main == "https://subscription.example.com/token-part/nested/test%20user/"
    assert json_url == f"{main}?format=json"
    assert clash_url == f"{main}?format=clash"


def test_partial_metadata_fallback_reconstructs_panel_subscription_uri():
    settings = {
        "success": True,
        "obj": {
            "subURI": "", "subDomain": "subscriptions.example.com", "subPort": "2096",
            "subPath": "/private/sub/", "subCertFile": "/cert.pem", "subKeyFile": "/key.pem",
        },
    }
    inbounds = {"success": True, "obj": {"inbounds": [{"id": 9, "tag": "vless"}, {"tag": "bad"}]}}

    assert extract_partial_metadata(settings, inbounds, "https://panel.example.com/private") == (
        "https://subscriptions.example.com:2096/private/sub",
        [{"id": 9, "tag": "vless"}],
    )


def test_partial_metadata_prefers_explicit_sub_uri_and_validates_port():
    assert build_subscription_base_from_settings(
        {"subURI": "https://sub.example.com:2096/custom/path/"}, "https://panel.example.com"
    ) == "https://sub.example.com:2096/custom/path"
    with pytest.raises(ValueError, match="port"):
        build_subscription_base_from_settings(
            {"subURI": "", "subPort": "70000", "subPath": "/sub"}, "https://panel.example.com"
        )


def test_blank_subscription_uri_uses_panel_host_and_default_subscription_listener():
    assert build_subscription_base_from_settings(
        {"subURI": "", "subDomain": "", "subPort": "2096", "subPath": "/sub/",
         "subKeyFile": "", "subCertFile": ""},
        "https://panel.example.com:2053/custom-panel-path",
    ) == "http://panel.example.com:2096/sub"
    assert build_subscription_base_from_settings(
        {"subURI": "", "subPort": "2096", "subPath": "subscription", "subKeyFile": "/key", "subCertFile": "/cert"},
        "https://[2001:db8::1]:2053/private-panel",
    ) == "https://[2001:db8::1]:2096/subscription"


def test_subscription_uri_preserves_ipv6_host_and_port():
    main, _, _ = build_subscription_urls("https://[2001:db8::1]:2096/sub", "alice")

    assert main == "https://[2001:db8::1]:2096/sub/alice/"


def test_subscription_url_rejects_embedded_credentials():
    with pytest.raises(ValueError, match="credentials"):
        build_subscription_urls("https://user:pass@example.com:2096/sub", "alice")


def test_subscription_url_rejects_invalid_port():
    with pytest.raises(ValueError, match="port"):
        build_subscription_urls("https://example.com:not-a-port/sub", "alice")


def test_web_panel_url_uses_configured_owner_route():
    assert build_web_panel_url("https://owner.example.com/private-dashboard", "test user", "Owner VPN") == (
        "https://owner.example.com/private-dashboard/test%20user?title=Owner%20VPN"
    )


@pytest.mark.parametrize("payload", [None, {}, {"success": False}, {"success": True, "obj": {}}])
def test_invalid_load_metadata_is_rejected(payload):
    with pytest.raises(ValueError):
        extract_load_metadata(payload)
