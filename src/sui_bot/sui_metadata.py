"""Parsing and URL helpers for S-UI metadata responses."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote, urlsplit, urlunsplit


def extract_load_metadata(data: dict[str, Any] | None) -> tuple[str, list[dict[str, Any]]]:
    if not data or data.get("success") is not True:
        raise ValueError("S-UI load response was not successful")
    obj = data.get("obj")
    if not isinstance(obj, dict):
        raise ValueError("S-UI load response has no object")
    sub_uri = str(obj.get("subURI") or "").strip()
    inbounds = obj.get("inbounds")
    if not sub_uri:
        raise ValueError("S-UI load response has no subURI")
    parsed = urlsplit(sub_uri)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("S-UI subURI is not an absolute HTTP(S) URL")
    if not isinstance(inbounds, list):
        raise ValueError("S-UI load response has no inbounds list")
    clean_inbounds = [item for item in inbounds if isinstance(item, dict) and item.get("id") is not None]
    return sub_uri.rstrip("/"), clean_inbounds


def build_web_panel_url(web_panel_base: str, username: str, display_name: str | None = None) -> str:
    parsed = urlsplit(web_panel_base)
    try:
        _ = parsed.port
    except ValueError as exc:
        raise ValueError("invalid web-panel base URL") from exc
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("invalid web-panel base URL")
    url = f"{web_panel_base.rstrip('/')}/{quote(username, safe='')}"
    if display_name:
        url = f"{url}?title={quote(display_name, safe='')}"
    return url


def replace_url_origin(url: str, public_origin: str) -> str:
    """Replace only scheme/netloc while retaining the S-UI subscription path."""
    parsed = urlsplit(url)
    origin = urlsplit(public_origin)
    try:
        _ = origin.port
    except ValueError as exc:
        raise ValueError("invalid public subscription origin") from exc
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("invalid subscription URL")
    if origin.scheme != "https" or not origin.hostname or origin.path not in {"", "/"}:
        raise ValueError("public subscription origin must be an HTTPS origin without a path")
    if origin.username or origin.password or origin.query or origin.fragment:
        raise ValueError("invalid public subscription origin")
    return urlunsplit((origin.scheme, origin.netloc, parsed.path, parsed.query, parsed.fragment))


def build_subscription_urls(
    subscription_base: str,
    username: str,
    *,
    remove_port: bool = False,
) -> tuple[str, str, str]:
    """Build user links, optionally omitting only the URL's explicit port."""
    parsed = urlsplit(subscription_base)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("invalid subscription base URL")
    try:
        _ = parsed.port
    except ValueError as exc:
        raise ValueError("invalid subscription base URL port") from exc
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("subscription base URL must not contain credentials")
    if remove_port:
        hostname = parsed.hostname
        if ":" in hostname:
            hostname = f"[{hostname}]"
        base = urlunsplit((parsed.scheme, hostname, parsed.path, parsed.query, parsed.fragment)).rstrip("/")
    else:
        base = subscription_base.rstrip("/")
    encoded_name = quote(username, safe="")
    main = f"{base}/{encoded_name}/"
    return main, f"{main}?format=json", f"{main}?format=clash"
