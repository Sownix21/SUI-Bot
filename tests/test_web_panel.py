import json

import pytest

from sui_bot.web_panel import (
    build_nginx_configuration,
    render_web_panel_html,
    subscription_metadata,
    validate_dashboard_port,
    validate_domain,
    validate_route,
    validate_upstream_host,
)


def test_subscription_metadata_and_nginx_are_server_specific(tmp_path) -> None:
    cache = tmp_path / "subscription_cache.json"
    cache.write_text(json.dumps({
        "subURI": "https://old.example.com:2096/secret-token/vpn-path",
        "timestamp": 1,
    }), encoding="utf-8")
    metadata = subscription_metadata(cache)
    config = build_nginx_configuration(
        domain="panel.new-owner.example",
        route="private-dashboard",
        metadata=metadata,
        certificate="/etc/letsencrypt/live/panel.new-owner.example/fullchain.pem",
        certificate_key="/etc/letsencrypt/live/panel.new-owner.example/privkey.pem",
        dashboard_port=2083,
    )

    assert metadata["port"] == 2096
    assert "127.0.0.1:2096" in config
    assert "listen 2083 ssl http2;" in config
    assert "listen 2096 ssl" not in config
    assert "/secret-token/vpn-path/" in config
    assert "203.0.113.10" not in config
    assert "private-owner.example" not in config
    assert "https://$host:2083/private-dashboard/" in config
    assert "ssl_certificate /etc/letsencrypt/" in config


def test_html_configuration_is_injected_as_json_without_private_defaults() -> None:
    template = "<script>const SETTINGS=__SUI_BOT_WEB_CONFIG__;</script>"
    rendered = render_web_panel_html(
        template,
        title='Owner "VPN"',
        route="owner-route",
        subscription_prefix="/secret/path",
    )
    assert '__SUI_BOT_WEB_CONFIG__' not in rendered
    assert 'Owner \\"VPN\\"' in rendered
    assert '"apiPrefix": "/owner-route/api"' in rendered


@pytest.mark.parametrize("value", ["127.0.0.1", "bad domain", "-bad.example.com", "example"])
def test_invalid_public_domains_are_rejected(value) -> None:
    with pytest.raises(ValueError):
        validate_domain(value)


@pytest.mark.parametrize("value", ["a", "has/slash", "bad route", "route;$bad"])
def test_unsafe_dashboard_routes_are_rejected(value) -> None:
    with pytest.raises(ValueError):
        validate_route(value)


def test_upstream_hosts_accept_vps_addresses_but_reject_nginx_syntax() -> None:
    assert validate_upstream_host("203.0.113.10") == "203.0.113.10"
    assert validate_upstream_host("::1") == "[::1]"
    with pytest.raises(ValueError):
        validate_upstream_host("127.0.0.1; include bad.conf")


@pytest.mark.parametrize("value", [80, 443, 2096, 0, 65536, "invalid"])
def test_dashboard_port_rejects_reserved_invalid_and_subscription_ports(value) -> None:
    with pytest.raises(ValueError):
        validate_dashboard_port(value, 2096)


def test_dashboard_port_is_separate_from_subscription_listener() -> None:
    assert validate_dashboard_port("2083", 2096) == 2083
