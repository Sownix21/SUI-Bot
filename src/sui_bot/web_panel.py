"""Pure validation and rendering helpers for the optional nginx web panel."""

from __future__ import annotations

import json
import ipaddress
import re
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlsplit

DOMAIN_PATTERN = re.compile(r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")
ROUTE_PATTERN = re.compile(r"^[A-Za-z0-9_-]{4,64}$")
RESERVED_PUBLIC_PORTS = {80, 443}


def validate_domain(value: str) -> str:
    domain = value.strip().rstrip(".").lower()
    if DOMAIN_PATTERN.fullmatch(domain) is None:
        raise ValueError("enter a valid public domain name, not an IP address")
    return domain


def validate_route(value: str) -> str:
    route = value.strip().strip("/")
    if ROUTE_PATTERN.fullmatch(route) is None:
        raise ValueError("route must contain 4-64 letters, numbers, underscores, or hyphens")
    return route


def validate_upstream_host(value: str) -> str:
    host = value.strip().strip("[]")
    try:
        parsed_ip = ipaddress.ip_address(host)
        return f"[{parsed_ip.compressed}]" if parsed_ip.version == 6 else parsed_ip.compressed
    except ValueError:
        if host == "localhost" or DOMAIN_PATTERN.fullmatch(host.lower()):
            return host.lower()
    raise ValueError("enter a valid S-UI upstream IP address or domain")


def validate_dashboard_port(value: int | str, subscription_port: int | str) -> int:
    try:
        port = int(value)
        upstream_port = int(subscription_port)
    except (TypeError, ValueError) as exc:
        raise ValueError("dashboard port must be a number between 1 and 65535") from exc
    if not 1 <= port <= 65535:
        raise ValueError("dashboard port must be between 1 and 65535")
    if port in RESERVED_PUBLIC_PORTS:
        raise ValueError("dashboard port must be different from public HTTP/HTTPS ports 80 and 443")
    if port == upstream_port:
        raise ValueError("dashboard port must be different from the S-UI subscription port")
    return port


def subscription_metadata(cache_path: str | Path) -> dict[str, Any]:
    source = Path(cache_path)
    if not source.is_file():
        raise ValueError("subscription cache is missing; start the bot once so /apiv2/load can be cached")
    try:
        data = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("subscription cache is not valid JSON") from exc
    uri = data.get("subURI") if isinstance(data, dict) else None
    if not isinstance(uri, str) or uri != uri.strip() or any(character.isspace() for character in uri):
        raise ValueError("subscription cache does not contain subURI")
    parsed = urlsplit(uri)
    try:
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
    except ValueError as exc:
        raise ValueError("cached subscription URI has an invalid port") from exc
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or not parsed.path.strip("/"):
        raise ValueError("cached subscription URI is not a usable HTTP(S) URL")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("cached subscription URI contains unsupported credentials, query, or fragment")
    return {
        "uri": uri.rstrip("/"),
        "scheme": parsed.scheme,
        "hostname": parsed.hostname,
        "port": port,
        "prefix": "/" + parsed.path.strip("/"),
    }


def render_web_panel_html(template: str, *, title: str, route: str, subscription_prefix: str) -> str:
    configuration = json.dumps({
        "title": title.strip() or "SUI Bot",
        "apiPrefix": f"/{validate_route(route)}/api",
        "subscriptionPrefix": subscription_prefix.rstrip("/"),
    }, ensure_ascii=False).replace("</", "<\\/")
    marker = "__SUI_BOT_WEB_CONFIG__"
    if template.count(marker) != 1:
        raise ValueError("web-panel template marker is missing or duplicated")
    return template.replace(marker, configuration)


def build_nginx_configuration(
    *,
    domain: str,
    route: str,
    metadata: dict[str, Any],
    certificate: str,
    certificate_key: str,
    upstream_host: str = "127.0.0.1",
    dashboard_port: int = 2083,
) -> str:
    domain = validate_domain(domain)
    route = validate_route(route)
    certificate_path = PurePosixPath(certificate).as_posix()
    key_path = PurePosixPath(certificate_key).as_posix()
    if not certificate_path.startswith("/") or not key_path.startswith("/"):
        raise ValueError("certificate paths must be absolute Linux paths")
    if any(character in certificate_path + key_path for character in "\n\r;{}"):
        raise ValueError("certificate paths contain unsafe characters")
    prefix = str(metadata["prefix"]).rstrip("/")
    if re.fullmatch(r"/[A-Za-z0-9._~%/-]+", prefix) is None:
        raise ValueError("subscription path cannot be represented safely in nginx")
    route_prefix = f"/{route}"
    if prefix == route_prefix or prefix.startswith(f"{route_prefix}/") or route_prefix.startswith(f"{prefix}/"):
        raise ValueError("dashboard route conflicts with the S-UI subscription path")
    scheme = str(metadata["scheme"])
    hostname = str(metadata["hostname"])
    port = int(metadata["port"])
    if scheme not in {"http", "https"} or not 1 <= port <= 65535:
        raise ValueError("S-UI upstream scheme or port is invalid")
    dashboard_port = validate_dashboard_port(dashboard_port, port)
    if re.fullmatch(r"[A-Za-z0-9.-]+", hostname) is None:
        raise ValueError("S-UI upstream hostname cannot be represented safely in nginx")
    upstream = f"{scheme}://{validate_upstream_host(upstream_host)}:{port}"
    ssl_proxy = ""
    if scheme == "https":
        ssl_proxy = f"""
        # Operator-confirmed same-VPS upstream: encryption is retained, while
        # certificate verification is handled at the public nginx TLS boundary.
        proxy_ssl_verify off;
        proxy_ssl_server_name on;
        proxy_ssl_name {hostname};"""
    return f"""# Managed by SUI Bot. Re-run `sudo sui-bot web-panel` to change it.
server {{
    listen 80;
    listen [::]:80;
    server_name {domain};

    location ^~ /.well-known/acme-challenge/ {{
        root /var/www/sui-bot;
    }}
    location = /{route} {{ return 302 https://$host:{dashboard_port}/{route}/; }}
    location ^~ /{route}/ {{ return 301 https://$host:{dashboard_port}$request_uri; }}
    location / {{
        return 301 https://$host$request_uri;
    }}
}}

server {{
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name {domain};

    ssl_certificate {certificate_path};
    ssl_certificate_key {key_path};
    ssl_protocols TLSv1.2 TLSv1.3;
    add_header X-Content-Type-Options nosniff always;
    add_header Referrer-Policy no-referrer always;
    add_header X-Frame-Options DENY always;
    add_header Permissions-Policy "camera=(), microphone=(), geolocation=()" always;
    add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; font-src 'self' https://cdn.jsdelivr.net data:; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'" always;

    # Clean subscription URLs: preserve the request URI and proxy to the
    # local S-UI listener, so clients never need the private S-UI port.
    location ^~ {prefix}/ {{
        proxy_pass {upstream};
        proxy_set_header Host {hostname};
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;{ssl_proxy}
    }}

    location / {{ return 404; }}
}}

server {{
    listen {dashboard_port} ssl http2;
    listen [::]:{dashboard_port} ssl http2;
    server_name {domain};

    ssl_certificate {certificate_path};
    ssl_certificate_key {key_path};
    ssl_protocols TLSv1.2 TLSv1.3;
    add_header X-Content-Type-Options nosniff always;
    add_header Referrer-Policy no-referrer always;
    add_header X-Frame-Options DENY always;
    add_header Permissions-Policy "camera=(), microphone=(), geolocation=()" always;
    add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; font-src 'self' https://cdn.jsdelivr.net data:; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'" always;

    # Same-origin data bridge used only by the dashboard on its dedicated port.
    location ^~ /{route}/api/ {{
        rewrite ^/{route}/api/(.*)$ {prefix}/$1 break;
        proxy_pass {upstream};
        proxy_set_header Host {hostname};
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;{ssl_proxy}
    }}

    location = /{route} {{ return 302 /{route}/; }}
    location = /{route}/ {{ return 404; }}
    location ~ ^/{route}/[^/]+/?$ {{
        root /var/www/sui-bot;
        try_files /index.html =404;
    }}

    location / {{ return 404; }}
}}
"""


def build_acme_nginx_configuration(domain: str) -> str:
    domain = validate_domain(domain)
    return f"""# Temporary SUI Bot ACME configuration.
server {{
    listen 80;
    listen [::]:80;
    server_name {domain};
    location ^~ /.well-known/acme-challenge/ {{ root /var/www/sui-bot; }}
    location / {{ return 404; }}
}}
"""
