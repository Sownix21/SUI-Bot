"""Authorization and transport-security helpers."""

from __future__ import annotations

import ipaddress
from collections.abc import Mapping, Sequence
from urllib.parse import urlsplit


def validate_service_url(url: str, *, allow_insecure_http: bool = False) -> str:
    if not isinstance(url, str) or not url or url != url.strip() or any(character.isspace() for character in url):
        raise RuntimeError("SUI_HOST must be an absolute HTTP(S) URL")
    try:
        parsed = urlsplit(url)
        hostname = parsed.hostname
        port = parsed.port
    except ValueError as exc:
        raise RuntimeError("SUI_HOST contains an invalid host or port") from exc
    if parsed.scheme not in {"http", "https"} or not hostname:
        raise RuntimeError("SUI_HOST must be an absolute HTTP(S) URL")
    if parsed.username or parsed.password:
        raise RuntimeError("SUI_HOST must not contain embedded credentials")
    if parsed.query or parsed.fragment:
        raise RuntimeError("SUI_HOST must not contain a query string or fragment")
    if port is not None and not 1 <= port <= 65535:
        raise RuntimeError("SUI_HOST contains an invalid port")
    if parsed.scheme == "http" and not allow_insecure_http:
        try:
            is_loopback = ipaddress.ip_address(hostname).is_loopback
        except ValueError:
            is_loopback = hostname.lower() == "localhost"
        if not is_loopback:
            raise RuntimeError(
                "SUI_HOST must use HTTPS for remote hosts; set ALLOW_INSECURE_HTTP=true only for a trusted private deployment"
            )
    return url.rstrip("/")


def can_access_client(
    user_id: int,
    client_id: int,
    assignments: Mapping[int, Sequence[int] | int],
    admin_id: int,
) -> bool:
    if user_id == admin_id:
        return True
    assigned = assignments.get(user_id)
    if isinstance(assigned, Sequence) and not isinstance(assigned, (str, bytes)):
        return client_id in assigned
    return assigned == client_id


PUBLIC_CALLBACK_ACTIONS = {"language_settings", "main_menu", "my_usage"}
PUBLIC_CALLBACK_PREFIXES = (
    "lang_set_",
    "my_usage_",
    "get_sub_links_",
    "select_sub_",
    "renew_start_",
    "renew_choose_",
    "renew_cancel_",
)


def is_public_callback(action: str) -> bool:
    """Return whether a callback is safe for a non-administrator to invoke."""
    return action in PUBLIC_CALLBACK_ACTIONS or action.startswith(PUBLIC_CALLBACK_PREFIXES)
