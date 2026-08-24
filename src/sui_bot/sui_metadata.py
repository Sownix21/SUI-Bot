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


def build_subscription_base_from_settings(settings: dict[str, Any], panel_base_url: str) -> str:
    """Reproduce S-UI's final subscription URI from its settings endpoint."""
    configured_uri = str(settings.get("subURI") or "").strip()
    if configured_uri:
        parsed_uri = urlsplit(configured_uri)
        if parsed_uri.scheme not in {"http", "https"} or not parsed_uri.hostname:
            raise ValueError("S-UI settings contain an invalid subURI")
        return configured_uri.rstrip("/")

    panel = urlsplit(panel_base_url)
    host = str(settings.get("subDomain") or panel.hostname or "").strip()
    if not host:
        raise ValueError("S-UI settings do not provide a subscription host")
    scheme = "https" if settings.get("subKeyFile") and settings.get("subCertFile") else "http"
    try:
        port = int(str(settings.get("subPort") or "0"))
    except ValueError as exc:
        raise ValueError("S-UI settings contain an invalid subscription port") from exc
    if not 1 <= port <= 65535:
        raise ValueError("S-UI settings contain an invalid subscription port")
    path = str(settings.get("subPath") or "/")
    if not path.startswith("/"):
        path = f"/{path}"
    display_host = f"[{host}]" if ":" in host and not host.startswith("[") else host
    netloc = display_host if (scheme, port) in {("http", 80), ("https", 443)} else f"{display_host}:{port}"
    return urlunsplit((scheme, netloc, path, "", "")).rstrip("/")


def extract_partial_metadata(
    settings_response: dict[str, Any] | None,
    inbounds_response: dict[str, Any] | None,
    panel_base_url: str,
) -> tuple[str, list[dict[str, Any]]]:
    """Extract metadata from the smaller API endpoints used if full load is malformed."""
    if not settings_response or settings_response.get("success") is not True:
        raise ValueError("S-UI settings response was not successful")
    if not inbounds_response or inbounds_response.get("success") is not True:
        raise ValueError("S-UI inbounds response was not successful")
    settings = settings_response.get("obj")
    inbounds_obj = inbounds_response.get("obj")
    if not isinstance(settings, dict) or not isinstance(inbounds_obj, dict):
        raise ValueError("S-UI partial metadata response has no object")
    inbounds = inbounds_obj.get("inbounds")
    if not isinstance(inbounds, list):
        raise ValueError("S-UI partial metadata response has no inbounds list")
    clean_inbounds = [item for item in inbounds if isinstance(item, dict) and item.get("id") is not None]
    return build_subscription_base_from_settings(settings, panel_base_url), clean_inbounds


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
