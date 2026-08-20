"""Environment-backed configuration for SUI Bot.

Secrets are deliberately never written by the application.  Deployment tooling
is responsible for creating a permission-restricted environment file.
"""

from __future__ import annotations

import os
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, TypeVar

from dotenv import load_dotenv

T = TypeVar("T")


def validate_display_name(value: Any) -> str:
    if not isinstance(value, str):
        raise RuntimeError("BOT_DISPLAY_NAME must be text")
    normalized = unicodedata.normalize("NFC", value.strip())
    if not 2 <= len(normalized) <= 48:
        raise RuntimeError("BOT_DISPLAY_NAME must contain 2-48 characters")
    if any(unicodedata.category(character).startswith("C") for character in normalized):
        raise RuntimeError("BOT_DISPLAY_NAME must not contain control or formatting characters")
    return normalized


def validate_optional_https_url(value: Any, name: str) -> str:
    normalized = str(value or "").strip().rstrip("/")
    if not normalized:
        return ""
    from urllib.parse import urlsplit

    try:
        parsed = urlsplit(normalized)
        _ = parsed.port
    except ValueError as exc:
        raise RuntimeError(f"{name} contains an invalid port") from exc
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise RuntimeError(f"{name} must be an absolute HTTPS URL without embedded credentials")
    if parsed.query or parsed.fragment:
        raise RuntimeError(f"{name} must not contain a query string or fragment")
    return normalized


def validate_optional_https_origin(value: Any, name: str) -> str:
    normalized = validate_optional_https_url(value, name)
    if normalized:
        from urllib.parse import urlsplit

        if urlsplit(normalized).path not in {"", "/"}:
            raise RuntimeError(f"{name} must not contain a path")
    return normalized


def _load_local_env() -> None:
    configured = os.getenv("SUI_BOT_ENV_FILE")
    if configured:
        load_dotenv(configured, override=False)
        return
    for candidate in (Path.cwd() / ".env", Path.cwd() / "sui-bot.env"):
        if candidate.is_file():
            load_dotenv(candidate, override=False)
            return


def env(name: str, default: Any = None, *, required: bool = False, cast: Callable[[Any], T] | None = None) -> Any | T:
    value = os.getenv(name, default)
    if required and (value is None or not str(value).strip()):
        raise RuntimeError(f"Missing required environment variable: {name}")
    if cast is not None and value is not None:
        try:
            return cast(value)
        except (TypeError, ValueError) as exc:
            raise RuntimeError(f"Invalid value for {name}") from exc
    return value


def env_bool(name: str, default: bool = False) -> bool:
    value = str(os.getenv(name, str(default))).strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    raise RuntimeError(f"Invalid boolean value for {name}")


@dataclass(frozen=True, slots=True)
class Settings:
    sui_host: str
    sui_token: str
    bot_token: str
    admin_telegram_id: int
    admin_client_id: int
    backup_dir: str
    db_name: str
    backup_max_bytes: int
    allow_insecure_http: bool
    rate_limit_window: int
    max_requests_per_window: int
    rate_limit_seconds: int
    block_duration: int
    redis_enabled: bool
    redis_host: str
    redis_port: int
    redis_db: int
    items_per_page: int
    sub_cache_file: str
    sub_cache_duration: int
    assignments_file: str
    metrics_file: str
    reminder_cooldown: int
    renewal_monthly_price: int
    renewal_month_options: str
    payment_card_number: str
    payment_card_holder: str
    bot_display_name: str
    hide_subscription_port: bool
    web_panel_base_url: str
    subscription_public_origin: str

    @classmethod
    def from_env(cls) -> "Settings":
        settings = cls(
            sui_host=str(env("SUI_HOST", required=True)),
            sui_token=str(env("SUI_TOKEN", required=True)),
            bot_token=str(env("BOT_TOKEN", required=True)),
            admin_telegram_id=env("ADMIN_TELEGRAM_ID", required=True, cast=int),
            admin_client_id=env("ADMIN_CLIENT_ID", 1, cast=int),
            backup_dir=str(env("BACKUP_DIR", "backups")),
            db_name=str(env("DB_NAME", "Sui")),
            backup_max_bytes=env("BACKUP_MAX_BYTES", 50 * 1024 * 1024, cast=int),
            allow_insecure_http=env_bool("ALLOW_INSECURE_HTTP", False),
            rate_limit_window=env("RATE_LIMIT_WINDOW", 60, cast=int),
            max_requests_per_window=env("MAX_REQUESTS_PER_WINDOW", 10, cast=int),
            rate_limit_seconds=env("RATE_LIMIT_SECONDS", 1, cast=int),
            block_duration=env("BLOCK_DURATION", 3600, cast=int),
            redis_enabled=env_bool("REDIS_ENABLED", False),
            redis_host=str(env("REDIS_HOST", "localhost")),
            redis_port=env("REDIS_PORT", 6379, cast=int),
            redis_db=env("REDIS_DB", 0, cast=int),
            items_per_page=env("ITEMS_PER_PAGE", 5, cast=int),
            sub_cache_file=str(env("SUB_CACHE_FILE", "subscription_cache.json")),
            sub_cache_duration=env("SUB_CACHE_DURATION", 24 * 60 * 60, cast=int),
            assignments_file=str(env("ASSIGNMENTS_FILE", "assignments.json")),
            metrics_file=str(env("METRICS_FILE", "metrics.json")),
            reminder_cooldown=env("REMINDER_COOLDOWN", 23 * 60 * 60, cast=int),
            renewal_monthly_price=env("RENEWAL_MONTHLY_PRICE", 100000, cast=int),
            renewal_month_options=str(env("RENEWAL_MONTH_OPTIONS", "1,2,3")),
            payment_card_number=str(env("PAYMENT_CARD_NUMBER", "0000-0000-0000-0000")),
            payment_card_holder=str(env("PAYMENT_CARD_HOLDER", "")),
            bot_display_name=validate_display_name(env("BOT_DISPLAY_NAME", "SUI Bot")),
            hide_subscription_port=env_bool("HIDE_SUBSCRIPTION_PORT", False),
            web_panel_base_url=validate_optional_https_url(env("WEB_PANEL_BASE_URL", ""), "WEB_PANEL_BASE_URL"),
            subscription_public_origin=validate_optional_https_origin(
                env("SUBSCRIPTION_PUBLIC_ORIGIN", ""), "SUBSCRIPTION_PUBLIC_ORIGIN"
            ),
        )
        settings.validate()
        return settings

    def validate(self) -> None:
        positive = {
            "ADMIN_TELEGRAM_ID": self.admin_telegram_id,
            "ADMIN_CLIENT_ID": self.admin_client_id,
            "BACKUP_MAX_BYTES": self.backup_max_bytes,
            "RATE_LIMIT_WINDOW": self.rate_limit_window,
            "MAX_REQUESTS_PER_WINDOW": self.max_requests_per_window,
            "BLOCK_DURATION": self.block_duration,
            "ITEMS_PER_PAGE": self.items_per_page,
            "SUB_CACHE_DURATION": self.sub_cache_duration,
            "REMINDER_COOLDOWN": self.reminder_cooldown,
            "RENEWAL_MONTHLY_PRICE": self.renewal_monthly_price,
        }
        for name, value in positive.items():
            if value <= 0:
                raise RuntimeError(f"{name} must be a positive integer")
        if self.rate_limit_seconds < 0:
            raise RuntimeError("RATE_LIMIT_SECONDS must be a non-negative integer")
        if not 1 <= self.redis_port <= 65535:
            raise RuntimeError("REDIS_PORT must be between 1 and 65535")
        if self.redis_db < 0:
            raise RuntimeError("REDIS_DB must be a non-negative integer")
        try:
            renewal_months = [int(value.strip()) for value in self.renewal_month_options.split(",") if value.strip()]
        except ValueError as exc:
            raise RuntimeError("RENEWAL_MONTH_OPTIONS must contain comma-separated positive integers") from exc
        if not renewal_months or any(month <= 0 for month in renewal_months):
            raise RuntimeError("RENEWAL_MONTH_OPTIONS must contain comma-separated positive integers")


_load_local_env()
