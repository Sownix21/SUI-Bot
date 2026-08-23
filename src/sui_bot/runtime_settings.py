"""Persistence for non-secret settings changed through the admin UI."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

ALLOWED_KEYS = {
    "RENEWAL_MONTHLY_PRICE",
    "RENEWAL_MONTH_OPTIONS",
    "PAYMENT_CARD_NUMBER",
    "PAYMENT_CARD_HOLDER",
    "BOT_DISPLAY_NAME",
    "HIDE_SUBSCRIPTION_PORT",
    "WEB_PANEL_ENABLED",
    "ADMIN_TIMEZONE",
    "PAYMENT_CURRENCY",
}


def load_runtime_settings(path: str = "runtime_settings.json") -> dict[str, Any]:
    source = Path(path)
    if not source.is_file():
        return {}
    data = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise RuntimeError("runtime settings must be a JSON object")
    return {key: value for key, value in data.items() if key in ALLOWED_KEYS}


def save_runtime_setting(name: str, value: str, path: str = "runtime_settings.json") -> None:
    if name not in ALLOWED_KEYS:
        raise ValueError(f"Refusing to persist secret or unsupported setting: {name}")
    destination = Path(path)
    data = load_runtime_settings(path)
    data[name] = value
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{destination.name}.", dir=destination.parent, text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, destination)
    except BaseException:
        Path(temporary_name).unlink(missing_ok=True)
        raise


def remove_runtime_setting(name: str, path: str = "runtime_settings.json") -> None:
    if name not in ALLOWED_KEYS:
        raise ValueError(f"Refusing to remove unsupported setting: {name}")
    destination = Path(path)
    data = load_runtime_settings(path)
    if name not in data:
        return
    data.pop(name)
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{destination.name}.", dir=destination.parent, text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, destination)
    except BaseException:
        Path(temporary_name).unlink(missing_ok=True)
        raise
