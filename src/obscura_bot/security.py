"""Authorization and transport-security helpers."""

from __future__ import annotations

import ipaddress
from collections.abc import Mapping, Sequence
from urllib.parse import urlsplit


def validate_service_url(url: str, *, allow_insecure_http: bool = False) -> str:
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise RuntimeError("SUI_HOST must be an absolute HTTP(S) URL")
    if parsed.username or parsed.password:
        raise RuntimeError("SUI_HOST must not contain embedded credentials")
    if parsed.scheme == "http" and not allow_insecure_http:
        try:
            is_loopback = ipaddress.ip_address(parsed.hostname).is_loopback
        except ValueError:
            is_loopback = parsed.hostname.lower() == "localhost"
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

