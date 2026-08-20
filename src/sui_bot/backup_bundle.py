"""Create and restore validated, non-secret SUI Bot state bundles."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .connection_guides import validate_guide_data

BUNDLE_FORMAT = "sui-bot-backup"
BUNDLE_VERSION = 1
MAX_BUNDLE_BYTES = 10 * 1024 * 1024
STATE_KEYS = frozenset({
    "assignments",
    "metrics",
    "languages",
    "runtime_settings",
    "subscription_cache",
    "inbounds_cache",
    "expired_notifications",
    "connection_guides",
})
RUNTIME_SETTING_KEYS = frozenset({
    "RENEWAL_MONTHLY_PRICE",
    "RENEWAL_MONTH_OPTIONS",
    "PAYMENT_CARD_NUMBER",
    "PAYMENT_CARD_HOLDER",
    "BOT_DISPLAY_NAME",
    "HIDE_SUBSCRIPTION_PORT",
    "WEB_PANEL_ENABLED",
})
LANGUAGE_CODES = frozenset({"en", "fa", "ru", "zh"})


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _checksum(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical(payload)).hexdigest()


def _validate_state_entry(key: str, value: Any) -> None:
    if not isinstance(value, (dict, list)):
        raise ValueError(f"invalid state entry: {key}")
    if key == "assignments":
        if not isinstance(value, dict):
            raise ValueError("assignments must be a JSON object")
        for telegram_id, assigned in value.items():
            try:
                valid_telegram_id = int(telegram_id) > 0
                client_ids = assigned if isinstance(assigned, list) else [assigned]
                valid_clients = bool(client_ids) and all(int(client_id) > 0 for client_id in client_ids)
            except (TypeError, ValueError):
                valid_telegram_id = valid_clients = False
            if not valid_telegram_id or not valid_clients:
                raise ValueError("assignments contain an invalid Telegram or client ID")
    elif key == "languages":
        if not isinstance(value, dict) or any(language not in LANGUAGE_CODES for language in value.values()):
            raise ValueError("language preferences contain an unsupported language")
        try:
            if any(int(user_id) <= 0 for user_id in value):
                raise ValueError
        except (TypeError, ValueError) as exc:
            raise ValueError("language preferences contain an invalid Telegram ID") from exc
    elif key == "runtime_settings":
        if not isinstance(value, dict) or set(value) - RUNTIME_SETTING_KEYS:
            raise ValueError("runtime settings contain unsupported keys")
        display_name = value.get("BOT_DISPLAY_NAME")
        if display_name is not None:
            normalized = unicodedata.normalize("NFC", display_name.strip()) if isinstance(display_name, str) else ""
            if not 2 <= len(normalized) <= 48 or any(
                unicodedata.category(character).startswith("C") for character in normalized
            ):
                raise ValueError("runtime settings contain an invalid bot display name")
        hide_port = value.get("HIDE_SUBSCRIPTION_PORT")
        if hide_port is not None and str(hide_port).strip().lower() not in {"true", "false"}:
            raise ValueError("runtime settings contain an invalid subscription-port setting")
        web_panel_enabled = value.get("WEB_PANEL_ENABLED")
        if web_panel_enabled is not None and str(web_panel_enabled).strip().lower() not in {"true", "false"}:
            raise ValueError("runtime settings contain an invalid web-panel setting")
    elif key == "connection_guides":
        validate_guide_data(value)
    elif key in {"metrics", "subscription_cache", "inbounds_cache", "expired_notifications"} and not isinstance(value, dict):
        raise ValueError(f"{key} must be a JSON object")


def build_bundle(state_paths: Mapping[str, str | Path], configuration: Mapping[str, Any]) -> dict[str, Any]:
    unknown = set(state_paths) - STATE_KEYS
    if unknown:
        raise ValueError(f"unsupported state keys: {', '.join(sorted(unknown))}")
    state: dict[str, Any] = {}
    for key, raw_path in state_paths.items():
        path = Path(raw_path)
        if not path.is_file():
            continue
        if path.stat().st_size > MAX_BUNDLE_BYTES:
            raise ValueError(f"state file is too large: {key}")
        value = json.loads(path.read_text(encoding="utf-8"))
        _validate_state_entry(key, value)
        state[key] = value
    payload: dict[str, Any] = {
        "format": BUNDLE_FORMAT,
        "version": BUNDLE_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "configuration": dict(configuration),
        "state": state,
    }
    payload["checksum_sha256"] = _checksum(payload)
    if len(_canonical(payload)) > MAX_BUNDLE_BYTES:
        raise ValueError("backup bundle exceeds the safety limit")
    return payload


def write_bundle(bundle: Mapping[str, Any], destination: str | Path) -> None:
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(bundle, ensure_ascii=False, indent=2).encode("utf-8")
    if len(encoded) > MAX_BUNDLE_BYTES:
        raise ValueError("backup bundle exceeds the safety limit")
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    except BaseException:
        Path(temporary_name).unlink(missing_ok=True)
        raise


def load_bundle(source: str | Path) -> dict[str, Any]:
    path = Path(source)
    if not path.is_file() or path.stat().st_size > MAX_BUNDLE_BYTES:
        raise ValueError("backup file is missing or exceeds the safety limit")
    try:
        bundle = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("backup file is not valid UTF-8 JSON") from exc
    if not isinstance(bundle, dict):
        raise ValueError("backup bundle must be a JSON object")
    if bundle.get("format") != BUNDLE_FORMAT or bundle.get("version") != BUNDLE_VERSION:
        raise ValueError("unsupported SUI Bot backup format or version")
    supplied_checksum = bundle.get("checksum_sha256")
    unsigned = {key: value for key, value in bundle.items() if key != "checksum_sha256"}
    if not isinstance(supplied_checksum, str) or supplied_checksum != _checksum(unsigned):
        raise ValueError("backup checksum is invalid; the file is damaged or modified")
    state = bundle.get("state")
    if not isinstance(state, dict) or set(state) - STATE_KEYS:
        raise ValueError("backup contains unsupported state entries")
    for key, value in state.items():
        _validate_state_entry(key, value)
    configuration = bundle.get("configuration")
    if not isinstance(configuration, dict):
        raise ValueError("backup configuration is invalid")
    return bundle


def restore_bundle(bundle: Mapping[str, Any], state_paths: Mapping[str, str | Path]) -> list[str]:
    state = bundle.get("state")
    if not isinstance(state, dict):
        raise ValueError("backup has no valid state section")
    unknown = set(state) - set(state_paths)
    if unknown:
        raise ValueError(f"no restore destination for: {', '.join(sorted(unknown))}")
    restored: list[str] = []
    for key, value in state.items():
        path = Path(state_paths[key])
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent, text=True)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(value, handle, ensure_ascii=False, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_name, path)
        except BaseException:
            Path(temporary_name).unlink(missing_ok=True)
            raise
        restored.append(key)
    return restored
