"""Linux administration CLI for the SUI Bot service."""

from __future__ import annotations

import argparse
import getpass
import json
import os
import re
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import dotenv_values

from .config import validate_display_name, validate_optional_https_origin, validate_optional_https_url
from .runtime_settings import load_runtime_settings, remove_runtime_setting, save_runtime_setting
from .security import validate_service_url
from .web_panel import (
    build_acme_nginx_configuration,
    build_nginx_configuration,
    render_web_panel_html,
    subscription_metadata,
    validate_dashboard_port,
    validate_domain,
    validate_route,
    validate_upstream_host,
)

SERVICE_NAME = "sui-bot.service"
DEFAULT_ENV_FILE = Path("/etc/sui-bot/sui-bot.env")
SERVICE_FILE = Path("/etc/systemd/system/sui-bot.service")
INSTALL_DIR = Path("/opt/sui-bot")
CONFIG_DIR = Path("/etc/sui-bot")
STATE_DIR = Path("/var/lib/sui-bot")
COMMAND_FILE = Path("/usr/local/bin/sui-bot")
WEB_ROOT = Path("/var/www/sui-bot")
WEB_PANEL_FILE = WEB_ROOT / "index.html"
NGINX_CONFIG = Path("/etc/nginx/conf.d/sui-bot-web-panel.conf")
SERVICE_USER = "sui-bot"
DEFAULT_REPOSITORY = "https://github.com/Sownix21/SUI-Bot.git"
SECRET_KEYS = {"BOT_TOKEN", "SUI_TOKEN"}
REQUIRED_KEYS = {"SUI_HOST", "SUI_TOKEN", "BOT_TOKEN", "ADMIN_TELEGRAM_ID"}
EDITABLE_FIELDS = [
    ("SUI_HOST", "S-UI URL"),
    ("SUI_TOKEN", "S-UI token"),
    ("BOT_TOKEN", "Telegram bot token"),
    ("ADMIN_TELEGRAM_ID", "Admin Telegram ID"),
    ("ADMIN_CLIENT_ID", "Admin client ID"),
    ("ALLOW_INSECURE_HTTP", "Allow insecure HTTP"),
    ("REDIS_ENABLED", "Enable Redis rate limiting"),
    ("REDIS_HOST", "Redis host"),
    ("REDIS_PORT", "Redis port"),
    ("REDIS_DB", "Redis database"),
    ("BACKUP_DIR", "Backup directory"),
    ("BACKUP_MAX_BYTES", "Maximum backup bytes"),
    ("RENEWAL_MONTHLY_PRICE", "Monthly renewal price"),
    ("RENEWAL_MONTH_OPTIONS", "Renewal month options"),
    ("PAYMENT_CARD_NUMBER", "Payment card number"),
    ("PAYMENT_CARD_HOLDER", "Payment card holder"),
    ("BOT_DISPLAY_NAME", "Message display name"),
    ("HIDE_SUBSCRIPTION_PORT", "Hide subscription-link port"),
    ("WEB_PANEL_BASE_URL", "Web-panel base URL"),
    ("SUBSCRIPTION_PUBLIC_ORIGIN", "Public subscription origin"),
]


def env_file() -> Path:
    return Path(os.getenv("SUI_BOT_SYSTEM_ENV_FILE", str(DEFAULT_ENV_FILE)))


def require_root(action: str) -> None:
    geteuid = getattr(os, "geteuid", None)
    if geteuid is None or geteuid() != 0:
        raise PermissionError(f"{action} requires root privileges. Run: sudo sui-bot")


def require_command(command: str) -> str:
    resolved = shutil.which(command)
    if resolved is None:
        raise RuntimeError(f"Required command not found: {command}")
    return resolved


def systemctl(action: str, *, check: bool = False) -> int:
    allowed_actions = {"status", "start", "stop", "restart", "enable", "disable"}
    if action not in allowed_actions:
        raise ValueError(f"Unsupported systemctl action: {action}")
    executable = require_command("systemctl")
    if action in {"start", "stop", "restart", "enable", "disable"}:
        require_root(f"systemctl {action}")
    result = subprocess.run([executable, action, SERVICE_NAME], check=check)  # noqa: S603 - fixed executable and allow-listed action
    return result.returncode


def show_logs(*, follow: bool = False, lines: int = 100) -> int:
    executable = require_command("journalctl")
    command = [executable, "--unit", SERVICE_NAME, "--no-pager", "--lines", str(max(1, lines))]
    if follow:
        command.extend(["--follow", "--output", "cat"])
    try:
        return subprocess.run(command, check=False).returncode  # noqa: S603 - fixed executable and constructed arguments
    except KeyboardInterrupt:
        return 130


def load_environment(path: Path | None = None) -> dict[str, str]:
    source = path or env_file()
    if not source.is_file():
        raise FileNotFoundError(f"Configuration file not found: {source}")
    return {key: "" if value is None else str(value) for key, value in dotenv_values(source).items()}


def _quoted(value: str) -> str:
    if "\n" in value or "\r" in value:
        raise ValueError("Environment values cannot contain newlines")
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def write_environment(values: dict[str, str], path: Path | None = None) -> None:
    require_root("Editing bot configuration")
    destination = path or env_file()
    destination.parent.mkdir(parents=True, exist_ok=True)
    ordered_keys = [key for key, _ in EDITABLE_FIELDS if key in values]
    ordered_keys.extend(sorted(set(values) - set(ordered_keys)))
    fd, temporary_name = tempfile.mkstemp(prefix=f".{destination.name}.", dir=destination.parent, text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            for key in ordered_keys:
                handle.write(f"{key}={_quoted(str(values[key]))}\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary_name, 0o600)
        os.replace(temporary_name, destination)
        os.chmod(destination, 0o600)
    except BaseException:
        Path(temporary_name).unlink(missing_ok=True)
        raise


def _bool_value(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off", ""}:
        return False
    raise ValueError("ALLOW_INSECURE_HTTP must be true or false")


def validate_environment(values: dict[str, str]) -> list[str]:
    errors = [f"Missing required value: {key}" for key in sorted(REQUIRED_KEYS) if not values.get(key, "").strip()]
    bot_token = values.get("BOT_TOKEN", "").strip()
    if bot_token and re.fullmatch(r"\d{5,}:[A-Za-z0-9_-]{20,}", bot_token) is None:
        errors.append("BOT_TOKEN does not have a valid Telegram bot-token format")
    try:
        admin_id = int(values.get("ADMIN_TELEGRAM_ID", "0"))
        if admin_id <= 0:
            raise ValueError
    except ValueError:
        errors.append("ADMIN_TELEGRAM_ID must be a positive integer")
    try:
        allow_http = _bool_value(values.get("ALLOW_INSECURE_HTTP", "false"))
        if values.get("SUI_HOST"):
            validate_service_url(values["SUI_HOST"], allow_insecure_http=allow_http)
    except (RuntimeError, ValueError) as exc:
        errors.append(str(exc))
    for boolean_key in ("REDIS_ENABLED", "HIDE_SUBSCRIPTION_PORT"):
        try:
            _bool_value(values.get(boolean_key, "false"))
        except ValueError:
            errors.append(f"{boolean_key} must be true or false")
    positive_keys = (
        "ADMIN_CLIENT_ID", "BACKUP_MAX_BYTES", "RATE_LIMIT_WINDOW", "MAX_REQUESTS_PER_WINDOW",
        "BLOCK_DURATION", "ITEMS_PER_PAGE", "SUB_CACHE_DURATION", "REMINDER_COOLDOWN",
        "RENEWAL_MONTHLY_PRICE",
    )
    for key in positive_keys:
        if values.get(key):
            try:
                if int(values[key]) <= 0:
                    raise ValueError
            except ValueError:
                errors.append(f"{key} must be a positive integer")
    for key in ("REDIS_DB", "RATE_LIMIT_SECONDS"):
        if values.get(key):
            try:
                if int(values[key]) < 0:
                    raise ValueError
            except ValueError:
                errors.append(f"{key} must be a non-negative integer")
    if values.get("REDIS_PORT"):
        try:
            if not 1 <= int(values["REDIS_PORT"]) <= 65535:
                raise ValueError
        except ValueError:
            errors.append("REDIS_PORT must be between 1 and 65535")
    if values.get("RENEWAL_MONTH_OPTIONS"):
        try:
            months = [int(item.strip()) for item in values["RENEWAL_MONTH_OPTIONS"].split(",") if item.strip()]
            if not months or any(month <= 0 for month in months):
                raise ValueError
        except ValueError:
            errors.append("RENEWAL_MONTH_OPTIONS must contain comma-separated positive integers")
    if values.get("BOT_DISPLAY_NAME"):
        try:
            validate_display_name(values["BOT_DISPLAY_NAME"])
        except RuntimeError as exc:
            errors.append(str(exc))
    for url_key in ("WEB_PANEL_BASE_URL", "SUBSCRIPTION_PUBLIC_ORIGIN"):
        if values.get(url_key):
            try:
                validator = validate_optional_https_origin if url_key == "SUBSCRIPTION_PUBLIC_ORIGIN" else validate_optional_https_url
                validator(values[url_key], url_key)
            except RuntimeError as exc:
                errors.append(str(exc))
    state_root = STATE_DIR.resolve()
    for key in ("BACKUP_DIR", "ASSIGNMENTS_FILE", "METRICS_FILE", "SUB_CACHE_FILE"):
        if not values.get(key, "").strip():
            continue
        configured = Path(values[key])
        resolved = configured.resolve() if configured.is_absolute() else (state_root / configured).resolve()
        if resolved != state_root and state_root not in resolved.parents:
            errors.append(f"{key} must stay inside {STATE_DIR}")
    return errors


def mask_value(key: str, value: str) -> str:
    if key not in SECRET_KEYS:
        return value
    if not value:
        return "<not set>"
    return "•" * 8 + (value[-4:] if len(value) > 4 else "")


def show_configuration() -> None:
    values = load_environment()
    print(f"\nConfiguration: {env_file()}\n")
    for key, label in EDITABLE_FIELDS:
        print(f"{label:28} {mask_value(key, values.get(key, '<default>'))}")


def validate_configuration() -> bool:
    errors = validate_environment(load_environment())
    if errors:
        print("Configuration errors:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return False
    print("Configuration is valid.")
    return True


def edit_configuration() -> None:
    require_root("Editing bot configuration")
    values = load_environment()
    while True:
        print("\nEditable settings (tokens are never displayed):")
        for index, (key, label) in enumerate(EDITABLE_FIELDS, 1):
            print(f"  {index:2}. {label:28} {mask_value(key, values.get(key, '<default>'))}")
        print("   0. Save and return")
        choice = input("Select a setting: ").strip()
        if choice == "0":
            errors = validate_environment(values)
            if errors:
                print("Cannot save yet:")
                for error in errors:
                    print(f"  - {error}")
                continue
            write_environment(values)
            print(f"Saved {env_file()} with mode 0600.")
            if input("Restart the bot now? [Y/n]: ").strip().lower() not in {"n", "no"}:
                systemctl("restart")
            return
        try:
            key, label = EDITABLE_FIELDS[int(choice) - 1]
        except (ValueError, IndexError):
            print("Invalid selection.")
            continue
        prompt = f"New {label} (blank keeps current; '-' clears optional values): "
        new_value = getpass.getpass(prompt) if key in SECRET_KEYS else input(prompt)
        if new_value == "":
            continue
        if new_value == "-" and key not in REQUIRED_KEYS:
            new_value = ""
        values[key] = new_value


def status_summary() -> str:
    executable = shutil.which("systemctl")
    if executable is None:
        return "systemd unavailable"
    result = subprocess.run(  # noqa: S603 - fixed executable and constant arguments
        [executable, "is-active", SERVICE_NAME],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() or "unknown"


def configured_data_path(values: dict[str, str], key: str, default: str) -> Path:
    configured = values.get(key, "").strip() or default
    path = Path(configured)
    return path if path.is_absolute() else STATE_DIR / path


def data_diagnostics() -> bool:
    """Show the exact runtime paths and validate migrated assignment data."""
    require_root("Running data diagnostics")
    values = load_environment()
    files = [
        ("Assignments", configured_data_path(values, "ASSIGNMENTS_FILE", "assignments.json")),
        ("Metrics", configured_data_path(values, "METRICS_FILE", "metrics.json")),
        ("Subscription cache", configured_data_path(values, "SUB_CACHE_FILE", "subscription_cache.json")),
        ("Inbound cache", STATE_DIR / "inbounds_cache.json"),
        ("Runtime settings", STATE_DIR / "runtime_settings.json"),
        ("Expiry state", STATE_DIR / "expired_notifications.json"),
        ("Connection guides", STATE_DIR / "connection_guides.json"),
    ]
    print(f"\nSUI Bot state directory: {STATE_DIR}")
    print(f"Exists: {STATE_DIR.exists()} | readable: {os.access(STATE_DIR, os.R_OK)} | writable: {os.access(STATE_DIR, os.W_OK)}")
    valid = True
    for label, path in files:
        if path.is_file():
            details = path.stat()
            print(f"  ✓ {label:20} {path} ({details.st_size} bytes, uid={details.st_uid}, gid={details.st_gid})")
        else:
            marker = "✗" if label == "Assignments" else "-"
            print(f"  {marker} {label:20} {path} (missing)")
            if label == "Assignments":
                valid = False

    assignments_path = files[0][1]
    if assignments_path.is_file():
        try:
            data = json.loads(assignments_path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and isinstance(data.get("telegram_clients"), dict):
                data = data["telegram_clients"]
            if not isinstance(data, dict):
                raise ValueError("top-level value must be a JSON object")
            users = 0
            links = 0
            for telegram_id, assigned in data.items():
                int(telegram_id)
                client_ids = assigned if isinstance(assigned, list) else [assigned]
                for client_id in client_ids:
                    if int(client_id) <= 0:
                        raise ValueError(f"invalid client ID for Telegram ID {telegram_id}")
                links += len(client_ids)
                users += 1
            print(f"\nAssignments JSON is valid: {users} Telegram user(s), {links} client link(s).")
        except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
            print(f"\nAssignments JSON is invalid: {exc}", file=sys.stderr)
            valid = False

    if not valid:
        print("\nExpected assignment destination:", assignments_path, file=sys.stderr)
        print("After copying, run: chown -R sui-bot:sui-bot /var/lib/sui-bot", file=sys.stderr)
    return valid


def _atomic_text_write(path: Path, content: str, mode: int = 0o644) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent, text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary_name, mode)
        os.replace(temporary_name, path)
    except BaseException:
        Path(temporary_name).unlink(missing_ok=True)
        raise


def _install_web_packages() -> None:
    if shutil.which("nginx") and shutil.which("certbot"):
        return
    print("nginx and Certbot are required for automatic HTTPS setup.")
    if input("Install the missing system packages now? [Y/n]: ").strip().lower() in {"n", "no"}:
        raise RuntimeError("install nginx and certbot, then run this option again")
    if shutil.which("apt-get"):
        apt = require_command("apt-get")
        subprocess.run([apt, "update"], check=True)  # noqa: S603 - fixed package manager arguments
        subprocess.run([apt, "install", "-y", "nginx", "certbot"], check=True)  # noqa: S603
    elif shutil.which("dnf"):
        dnf = require_command("dnf")
        subprocess.run([dnf, "install", "-y", "nginx", "certbot"], check=True)  # noqa: S603
    elif shutil.which("yum"):
        yum = require_command("yum")
        subprocess.run([yum, "install", "-y", "nginx", "certbot"], check=True)  # noqa: S603
    else:
        raise RuntimeError("automatic web-panel setup supports apt, dnf, or yum package managers")


def _ensure_tcp_port_available(port: int) -> None:
    """Reject a dashboard port already bound by a non-managed process."""
    addresses = [(socket.AF_INET, ("0.0.0.0", port))]  # noqa: S104 - availability probe, never listens
    if socket.has_ipv6:
        addresses.append((socket.AF_INET6, ("::", port)))
    for family, address in addresses:
        probe = socket.socket(family, socket.SOCK_STREAM)
        try:
            probe.bind(address)
        except OSError as exc:
            raise RuntimeError(
                f"dashboard port {port} is already occupied; choose a different unused port"
            ) from exc
        finally:
            probe.close()


def _nginx_test_and_reload() -> None:
    nginx = require_command("nginx")
    subprocess.run([nginx, "-t"], check=True)  # noqa: S603 - fixed executable and arguments
    systemctl_executable = require_command("systemctl")
    subprocess.run([systemctl_executable, "enable", "--now", "nginx"], check=True)  # noqa: S603
    subprocess.run([systemctl_executable, "reload", "nginx"], check=True)  # noqa: S603


def _web_template_path() -> Path:
    installed = INSTALL_DIR / "deploy" / "web-panel" / "index.html"
    if installed.is_file():
        return installed
    development = Path(__file__).resolve().parents[2] / "deploy" / "web-panel" / "index.html"
    if development.is_file():
        return development
    raise RuntimeError("web-panel HTML template is missing from this installation")


def web_panel_status() -> str:
    if NGINX_CONFIG.is_file() and WEB_PANEL_FILE.is_file():
        try:
            base_url = load_environment().get("WEB_PANEL_BASE_URL", "")
        except FileNotFoundError:
            base_url = ""
        return f"installed ({base_url or 'URL not configured'})"
    return "not installed"


def configure_web_panel() -> None:
    """Install a dedicated-domain HTTPS dashboard and clean subscription proxy."""
    require_root("Configuring the SUI Bot web panel")
    values = load_environment()
    cache_path = configured_data_path(values, "SUB_CACHE_FILE", "subscription_cache.json")
    metadata = subscription_metadata(cache_path)
    print("\nThis setup requires:")
    print("  - a dedicated domain whose DNS A/AAAA record points to this VPS")
    print("  - inbound TCP ports 80 and 443")
    print("  - S-UI listening on this same VPS")
    print("It will create a separate nginx site and will not overwrite nginx's default site.")
    if input("Continue? [y/N]: ").strip().lower() not in {"y", "yes"}:
        print("Web-panel setup cancelled.")
        return

    existing_web_url = urlsplit(values.get("WEB_PANEL_BASE_URL", ""))
    domain_default = existing_web_url.hostname or ""
    domain_prompt = f"Public dashboard domain [{domain_default}]: " if domain_default else "Public dashboard domain: "
    domain = validate_domain(input(domain_prompt).strip() or domain_default)
    default_title = values.get("BOT_DISPLAY_NAME", "SUI Bot") or "SUI Bot"
    title = input(f"Dashboard title [{default_title}]: ").strip() or default_title
    if len(title) > 80 or any(character in title for character in "\r\n"):
        raise ValueError("dashboard title must contain at most 80 characters on one line")
    default_route = existing_web_url.path.strip("/") or secrets.token_urlsafe(12)
    route = validate_route(input(f"Private dashboard route [{default_route}]: ").strip() or default_route)
    default_dashboard_port = existing_web_url.port or 2083
    dashboard_port = validate_dashboard_port(
        input(f"Dedicated HTTPS dashboard port [{default_dashboard_port}]: ").strip() or default_dashboard_port,
        metadata["port"],
    )
    print(
        f"Dashboard port {dashboard_port} must be unused by other services and allowed through the VPS firewall."
    )
    upstream_host = validate_upstream_host(
        input("Same-VPS S-UI subscription listener IP/host [127.0.0.1]: ").strip() or "127.0.0.1"
    )
    try:
        with socket.create_connection((upstream_host.strip("[]"), int(metadata["port"])), timeout=5):
            pass
    except OSError as exc:
        raise RuntimeError(
            f"S-UI subscription listener is unreachable at {upstream_host}:{metadata['port']}"
        ) from exc

    _install_web_packages()
    nginx = require_command("nginx")
    existing_web_domain = urlsplit(values.get("WEB_PANEL_BASE_URL", "")).hostname
    dump = subprocess.run(  # noqa: S603 - nginx configuration inspection
        [nginx, "-T"], check=False, capture_output=True, text=True,
    )
    if dump.returncode != 0:
        raise RuntimeError("existing nginx configuration is invalid; fix `nginx -t` errors before continuing")
    domain_blocks = re.findall(rf"\bserver_name\s+{re.escape(domain)}(?:\s|;)", dump.stdout + dump.stderr)
    managed_allowance = 0
    if NGINX_CONFIG.exists() and existing_web_domain == domain:
        managed_text = NGINX_CONFIG.read_text(encoding="utf-8", errors="replace")
        managed_allowance = len(re.findall(rf"\bserver_name\s+{re.escape(domain)}(?:\s|;)", managed_text))
    if len(domain_blocks) > managed_allowance:
        raise RuntimeError(f"nginx already contains another server block for {domain}; use a dedicated unused domain")
    listen_pattern = rf"\blisten\s+(?:\[::\]:)?{dashboard_port}(?:\s|;)"
    port_blocks = re.findall(listen_pattern, dump.stdout + dump.stderr)
    managed_port_allowance = 0
    if NGINX_CONFIG.exists() and existing_web_domain == domain and existing_web_url.port == dashboard_port:
        managed_port_allowance = len(re.findall(listen_pattern, managed_text))
    if len(port_blocks) > managed_port_allowance:
        raise RuntimeError(
            f"nginx already uses dashboard port {dashboard_port}; choose a different unused port"
        )
    if managed_port_allowance == 0:
        _ensure_tcp_port_available(dashboard_port)

    certificate = Path(f"/etc/letsencrypt/live/{domain}/fullchain.pem")
    certificate_key = Path(f"/etc/letsencrypt/live/{domain}/privkey.pem")
    old_config = NGINX_CONFIG.read_bytes() if NGINX_CONFIG.is_file() else None
    old_html = WEB_PANEL_FILE.read_bytes() if WEB_PANEL_FILE.is_file() else None
    old_environment = dict(values)
    runtime_path = STATE_DIR / "runtime_settings.json"
    old_runtime_settings = load_runtime_settings(str(runtime_path))
    environment_written = False
    runtime_written = False
    try:
        WEB_ROOT.mkdir(parents=True, exist_ok=True)
        os.chmod(WEB_ROOT, 0o755)  # noqa: S103 - nginx must traverse the public static web root
        (WEB_ROOT / ".well-known" / "acme-challenge").mkdir(parents=True, exist_ok=True)
        if not certificate.is_file() or not certificate_key.is_file():
            email = input("Email for Let's Encrypt expiry notices: ").strip()
            if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
                raise ValueError("enter a valid email address for Let's Encrypt")
            _atomic_text_write(NGINX_CONFIG, build_acme_nginx_configuration(domain))
            _nginx_test_and_reload()
            certbot = require_command("certbot")
            subprocess.run([  # noqa: S603 - validated domain/email and fixed Certbot mode
                certbot, "certonly", "--webroot", "--webroot-path", str(WEB_ROOT),
                "--domain", domain, "--email", email, "--agree-tos", "--non-interactive",
            ], check=True)

        template = _web_template_path().read_text(encoding="utf-8")
        html = render_web_panel_html(
            template,
            title=title,
            route=route,
            subscription_prefix=metadata["prefix"],
        )
        config = build_nginx_configuration(
            domain=domain,
            route=route,
            metadata=metadata,
            certificate=str(certificate),
            certificate_key=str(certificate_key),
            upstream_host=upstream_host,
            dashboard_port=dashboard_port,
        )
        _atomic_text_write(WEB_PANEL_FILE, html)
        _atomic_text_write(NGINX_CONFIG, config)
        _nginx_test_and_reload()

        values["WEB_PANEL_BASE_URL"] = f"https://{domain}:{dashboard_port}/{route}"
        values["SUBSCRIPTION_PUBLIC_ORIGIN"] = f"https://{domain}"
        values["HIDE_SUBSCRIPTION_PORT"] = "true"
        write_environment(values)
        environment_written = True
        save_runtime_setting("HIDE_SUBSCRIPTION_PORT", "true", str(runtime_path))
        runtime_written = True
        if shutil.which("chown"):
            shutil.chown(runtime_path, user=SERVICE_USER, group=SERVICE_USER)
        if systemctl("restart") != 0:
            raise RuntimeError("SUI Bot failed to restart with the web-panel configuration")
    except BaseException:
        if old_config is None:
            NGINX_CONFIG.unlink(missing_ok=True)
        else:
            NGINX_CONFIG.write_bytes(old_config)
        if old_html is None:
            WEB_PANEL_FILE.unlink(missing_ok=True)
        else:
            WEB_PANEL_FILE.write_bytes(old_html)
        if environment_written:
            write_environment(old_environment)
        if runtime_written:
            if "HIDE_SUBSCRIPTION_PORT" in old_runtime_settings:
                save_runtime_setting(
                    "HIDE_SUBSCRIPTION_PORT",
                    str(old_runtime_settings["HIDE_SUBSCRIPTION_PORT"]),
                    str(runtime_path),
                )
            else:
                remove_runtime_setting("HIDE_SUBSCRIPTION_PORT", str(runtime_path))
            if shutil.which("chown"):
                shutil.chown(runtime_path, user=SERVICE_USER, group=SERVICE_USER)
        try:
            _nginx_test_and_reload()
        except (OSError, subprocess.SubprocessError):
            pass
        if environment_written:
            systemctl("restart")
        raise

    print("\nSUI Bot web panel enabled successfully.")
    print(f"User URL format: https://{domain}:{dashboard_port}/{route}/<S-UI-username>")
    print("Clean portless subscription URLs were enabled automatically.")


def remove_web_panel(*, confirmed: bool = False) -> None:
    require_root("Removing the SUI Bot web panel")
    if not confirmed and input("Remove the SUI Bot nginx site and dashboard files? [y/N]: ").strip().lower() not in {"y", "yes"}:
        print("Web-panel removal cancelled.")
        return
    values = load_environment()
    runtime_path = STATE_DIR / "runtime_settings.json"
    old_config = NGINX_CONFIG.read_bytes() if NGINX_CONFIG.is_file() else None
    old_environment = dict(values)
    old_runtime_settings = load_runtime_settings(str(runtime_path))
    environment_written = False
    runtime_written = False
    try:
        NGINX_CONFIG.unlink(missing_ok=True)
        if shutil.which("nginx"):
            _nginx_test_and_reload()
        values["WEB_PANEL_BASE_URL"] = ""
        values["SUBSCRIPTION_PUBLIC_ORIGIN"] = ""
        values["HIDE_SUBSCRIPTION_PORT"] = "false"
        write_environment(values)
        environment_written = True
        save_runtime_setting("HIDE_SUBSCRIPTION_PORT", "false", str(runtime_path))
        runtime_written = True
        if shutil.which("chown"):
            shutil.chown(runtime_path, user=SERVICE_USER, group=SERVICE_USER)
        if systemctl("restart") != 0:
            raise RuntimeError("SUI Bot failed to restart after web-panel removal")
    except BaseException:
        if old_config is not None:
            NGINX_CONFIG.parent.mkdir(parents=True, exist_ok=True)
            NGINX_CONFIG.write_bytes(old_config)
            if shutil.which("nginx"):
                try:
                    _nginx_test_and_reload()
                except (OSError, subprocess.SubprocessError):
                    pass
        if environment_written:
            write_environment(old_environment)
        if runtime_written:
            if "HIDE_SUBSCRIPTION_PORT" in old_runtime_settings:
                save_runtime_setting(
                    "HIDE_SUBSCRIPTION_PORT",
                    str(old_runtime_settings["HIDE_SUBSCRIPTION_PORT"]),
                    str(runtime_path),
                )
            else:
                remove_runtime_setting("HIDE_SUBSCRIPTION_PORT", str(runtime_path))
            if shutil.which("chown"):
                shutil.chown(runtime_path, user=SERVICE_USER, group=SERVICE_USER)
        if environment_written:
            systemctl("restart")
        raise
    if WEB_ROOT.exists() and WEB_ROOT.resolve() == Path("/var/www/sui-bot"):
        shutil.rmtree(WEB_ROOT)
    print("SUI Bot web panel removed. Let's Encrypt certificates were retained for safety.")


def update_bot(*, confirmed: bool = False) -> None:
    """Clone the latest GitHub revision and run its idempotent installer."""
    require_root("Updating SUI Bot")
    repository = os.getenv("SUI_BOT_REPOSITORY", DEFAULT_REPOSITORY)
    if not confirmed:
        print(f"Latest source: {repository}")
        if input("Download and install the latest SUI Bot version? [Y/n]: ").strip().lower() in {"n", "no"}:
            print("Update cancelled.")
            return
    git = require_command("git")
    bash = require_command("bash")
    try:
        with tempfile.TemporaryDirectory(prefix="sui-bot-update-") as temporary_dir:
            subprocess.run([git, "clone", "--depth", "1", repository, temporary_dir], check=True)  # noqa: S603
            installer = Path(temporary_dir) / "scripts" / "install.sh"
            if not installer.is_file():
                raise RuntimeError("Downloaded repository does not contain scripts/install.sh")
            subprocess.run([bash, str(installer)], check=True)  # noqa: S603
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"Update failed with exit code {exc.returncode}") from exc
    print("SUI Bot was updated successfully. Reopen sui-bot to use the latest management menu.")


def uninstall_bot(*, confirmed: bool = False) -> None:
    """Completely remove SUI Bot after an explicit confirmation."""
    require_root("Uninstalling SUI Bot")
    if not confirmed:
        print("\nWARNING: This permanently removes SUI Bot and all of its local data, including:")
        print(f"  - Application:   {INSTALL_DIR}")
        print(f"  - Configuration: {CONFIG_DIR}")
        print(f"  - State/backups: {STATE_DIR}")
        print(f"  - Service:       {SERVICE_FILE}")
        print(f"  - Command:       {COMMAND_FILE}")
        print(f"  - System user:   {SERVICE_USER}")
        print(f"  - Web panel:     {WEB_ROOT} and {NGINX_CONFIG}")
        print("  - Let's Encrypt certificates and shared nginx packages are retained")
        confirmation = input("\nType UNINSTALL SUI BOT to continue: ").strip()
        if confirmation != "UNINSTALL SUI BOT":
            print("Uninstallation cancelled.")
            return

    systemctl_executable = require_command("systemctl")
    subprocess.run([systemctl_executable, "stop", SERVICE_NAME], check=False)  # noqa: S603
    subprocess.run([systemctl_executable, "disable", SERVICE_NAME], check=False)  # noqa: S603
    subprocess.run([systemctl_executable, "reset-failed", SERVICE_NAME], check=False)  # noqa: S603

    SERVICE_FILE.unlink(missing_ok=True)
    COMMAND_FILE.unlink(missing_ok=True)
    NGINX_CONFIG.unlink(missing_ok=True)
    if WEB_ROOT.exists() and WEB_ROOT.resolve() == Path("/var/www/sui-bot"):
        shutil.rmtree(WEB_ROOT)
    for directory in (INSTALL_DIR, CONFIG_DIR, STATE_DIR):
        if directory.is_symlink():
            directory.unlink()
        elif directory.exists():
            shutil.rmtree(directory)

    subprocess.run([systemctl_executable, "daemon-reload"], check=False)  # noqa: S603
    if shutil.which("nginx"):
        subprocess.run([require_command("nginx"), "-t"], check=False)  # noqa: S603
        subprocess.run([systemctl_executable, "reload", "nginx"], check=False)  # noqa: S603

    userdel = shutil.which("userdel")
    if userdel:
        subprocess.run([userdel, SERVICE_USER], check=False)  # noqa: S603
    groupdel = shutil.which("groupdel")
    if groupdel:
        subprocess.run([groupdel, SERVICE_USER], check=False)  # noqa: S603

    print("\nSUI Bot and all managed components were completely uninstalled.")


def interactive_menu() -> int:
    actions = {
        "1": lambda: systemctl("status"),
        "2": lambda: systemctl("start"),
        "3": lambda: systemctl("stop"),
        "4": lambda: systemctl("restart"),
        "5": lambda: show_logs(follow=True),
        "6": lambda: show_logs(follow=False, lines=100),
        "7": edit_configuration,
        "8": show_configuration,
        "9": validate_configuration,
        "10": update_bot,
        "11": data_diagnostics,
        "12": configure_web_panel,
        "13": remove_web_panel,
        "14": uninstall_bot,
    }
    while True:
        print("\n╭──────────────────────────────────────╮")
        print("│          SUI Bot Administration      │")
        print("╰──────────────────────────────────────╯")
        print(f"Service status: {status_summary()}\n")
        print(f"Web panel:     {web_panel_status()}\n")
        print("  1. Detailed status")
        print("  2. Start bot")
        print("  3. Stop bot")
        print("  4. Restart bot")
        print("  5. Follow live logs")
        print("  6. Show recent logs")
        print("  7. Modify credentials/settings")
        print("  8. Show configuration (secrets masked)")
        print("  9. Validate configuration")
        print(" 10. Update SUI Bot from GitHub")
        print(" 11. Diagnose assignments and data")
        print(" 12. Install/update web panel and nginx proxy")
        print(" 13. Remove web panel and nginx proxy")
        print(" 14. Completely uninstall SUI Bot")
        print("  0. Exit")
        choice = input("\nSelect an option: ").strip()
        if choice == "0":
            return 0
        action = actions.get(choice)
        if action is None:
            print("Invalid selection.")
            continue
        try:
            action()
        except (FileNotFoundError, PermissionError, RuntimeError, ValueError, subprocess.SubprocessError) as exc:
            print(f"Error: {exc}", file=sys.stderr)
        input("\nPress Enter to return to the menu...")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sui-bot", description="Manage the SUI Bot systemd service")
    subparsers = parser.add_subparsers(dest="command")
    for command in ("status", "start", "stop", "restart"):
        subparsers.add_parser(command)
    logs = subparsers.add_parser("logs")
    logs.add_argument("-f", "--follow", action="store_true")
    logs.add_argument("-n", "--lines", type=int, default=100)
    subparsers.add_parser("config", help="Interactively edit credentials and settings")
    subparsers.add_parser("show-config", help="Display configuration with secrets masked")
    subparsers.add_parser("validate", help="Validate the environment file")
    subparsers.add_parser("doctor", help="Validate assignment and runtime data files")
    subparsers.add_parser("update", help="Download and install the latest version from GitHub")
    subparsers.add_parser("web-panel", help="Install or update the optional HTTPS web panel")
    subparsers.add_parser("remove-web-panel", help="Remove the optional web panel and managed nginx site")
    subparsers.add_parser("uninstall", help="Completely uninstall SUI Bot and its managed data")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command is None:
            return interactive_menu()
        if args.command in {"status", "start", "stop", "restart"}:
            return systemctl(args.command)
        if args.command == "logs":
            return show_logs(follow=args.follow, lines=max(1, args.lines))
        if args.command == "config":
            edit_configuration()
            return 0
        if args.command == "show-config":
            show_configuration()
            return 0
        if args.command == "validate":
            return 0 if validate_configuration() else 1
        if args.command == "doctor":
            return 0 if data_diagnostics() else 1
        if args.command == "update":
            update_bot()
            return 0
        if args.command == "web-panel":
            configure_web_panel()
            return 0
        if args.command == "remove-web-panel":
            remove_web_panel()
            return 0
        if args.command == "uninstall":
            uninstall_bot()
            return 0
    except (FileNotFoundError, PermissionError, RuntimeError, ValueError, subprocess.SubprocessError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 2


def run() -> None:
    raise SystemExit(main())


if __name__ == "__main__":
    run()
