"""Pure helpers used by reminder/report jobs."""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any


def expiring_clients_with_assignments(
    clients: Iterable[dict[str, Any]],
    client_to_telegram: Mapping[int, list[int]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return per-user records and expiring clients with no Telegram assignment."""
    linked: list[dict[str, Any]] = []
    unlinked: list[dict[str, Any]] = []
    for client in clients:
        expiry = client.get("expiry", 0)
        client_id = client.get("id")
        if not client_id or not expiry:
            continue
        record = {
            "client_id": client_id,
            "name": client.get("name", "Unknown"),
            "desc": client.get("desc", "No description"),
            "expiry": expiry,
            "enable": client.get("enable", True),
        }
        telegram_ids = client_to_telegram.get(client_id, [])
        if not telegram_ids:
            unlinked.append(record)
            continue
        linked.extend({"tg_id": telegram_id, **record} for telegram_id in telegram_ids)
    return linked, unlinked


def load_expired_notification_ids(filepath: str) -> set[int]:
    source = Path(filepath)
    if not source.is_file():
        return set()
    data = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return set()
    current = data.get("notified_client_ids")
    if isinstance(current, list):
        return set(current)
    result: set[int] = set()
    for value in data.values():
        if isinstance(value, list):
            result.update(value)
    return result


def save_expired_notification_ids(filepath: str, client_ids: set[int], updated_at: str) -> None:
    Path(filepath).write_text(
        json.dumps({"notified_client_ids": sorted(client_ids), "updated_at": updated_at}, indent=2),
        encoding="utf-8",
    )
