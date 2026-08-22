"""Validated persistence for administrator-authored connection guides."""

from __future__ import annotations

import json
import os
import re
import secrets
import tempfile
import unicodedata
from pathlib import Path
from typing import Any, Mapping

MAX_GUIDES = 20
MAX_MESSAGES_PER_GUIDE = 30
MAX_TITLE_LENGTH = 48
MAX_TEXT_LENGTH = 32768
MAX_CAPTION_LENGTH = 1024
TELEGRAM_TEXT_LENGTH = 4096
MESSAGE_TYPES = frozenset({"text", "photo", "video", "document"})
GUIDE_ID_PATTERN = re.compile(r"^[a-f0-9]{12}$")


def split_guide_text(text: str, limit: int = TELEGRAM_TEXT_LENGTH) -> list[str]:
    """Split administrator-authored text without losing or changing its contents."""
    if limit < 1:
        raise ValueError("text chunk limit must be positive")
    chunks: list[str] = []
    remaining = text
    while len(remaining) > limit:
        boundary = remaining.rfind("\n", 0, limit)
        if boundary <= 0:
            boundary = limit
        else:
            boundary += 1
        chunks.append(remaining[:boundary])
        remaining = remaining[boundary:]
    if remaining:
        chunks.append(remaining)
    return chunks


def _has_unsafe_control(value: str) -> bool:
    return any(character not in {"\n", "\t"} and unicodedata.category(character).startswith("C") for character in value)


def empty_guide_data() -> dict[str, Any]:
    return {"version": 1, "enabled": False, "guides": []}


def validate_guide_message(message: Any) -> dict[str, str]:
    if not isinstance(message, Mapping):
        raise ValueError("guide message must be an object")
    message_type = message.get("type")
    if message_type not in MESSAGE_TYPES:
        raise ValueError("guide message has an unsupported type")
    if message_type == "text":
        text = message.get("text")
        if not isinstance(text, str) or not text.strip() or len(text) > MAX_TEXT_LENGTH or _has_unsafe_control(text):
            raise ValueError("guide text is empty or too long")
        if set(message) != {"type", "text"}:
            raise ValueError("guide text contains unsupported fields")
        return {"type": "text", "text": text}
    file_id = message.get("file_id")
    caption = message.get("caption", "")
    if not isinstance(file_id, str) or not 1 <= len(file_id) <= 512 or _has_unsafe_control(file_id):
        raise ValueError("guide media has an invalid Telegram file ID")
    if not isinstance(caption, str) or len(caption) > MAX_CAPTION_LENGTH or _has_unsafe_control(caption):
        raise ValueError("guide media caption is too long")
    if set(message) - {"type", "file_id", "caption"}:
        raise ValueError("guide media contains unsupported fields")
    return {"type": str(message_type), "file_id": file_id, "caption": caption}


def validate_guide_data(data: Any) -> dict[str, Any]:
    if not isinstance(data, Mapping) or set(data) != {"version", "enabled", "guides"}:
        raise ValueError("connection-guide data has an invalid structure")
    if data.get("version") != 1 or not isinstance(data.get("enabled"), bool):
        raise ValueError("connection-guide data has an invalid version or state")
    guides = data.get("guides")
    if not isinstance(guides, list) or len(guides) > MAX_GUIDES:
        raise ValueError("connection-guide list is invalid or too large")
    if data.get("enabled") and not guides:
        raise ValueError("enabled connection guides must contain at least one guide")
    clean_guides: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for guide in guides:
        if not isinstance(guide, Mapping) or set(guide) != {"id", "title", "messages"}:
            raise ValueError("connection guide has an invalid structure")
        guide_id = guide.get("id")
        title = guide.get("title")
        messages = guide.get("messages")
        if not isinstance(guide_id, str) or GUIDE_ID_PATTERN.fullmatch(guide_id) is None or guide_id in seen_ids:
            raise ValueError("connection guide has an invalid or duplicate ID")
        if (
            not isinstance(title, str)
            or not title.strip()
            or len(title.strip()) > MAX_TITLE_LENGTH
            or _has_unsafe_control(title)
        ):
            raise ValueError("connection guide has an invalid title")
        if not isinstance(messages, list) or not messages or len(messages) > MAX_MESSAGES_PER_GUIDE:
            raise ValueError("connection guide must contain 1-30 messages")
        seen_ids.add(guide_id)
        clean_guides.append({
            "id": guide_id,
            "title": title.strip(),
            "messages": [validate_guide_message(message) for message in messages],
        })
    return {"version": 1, "enabled": bool(data["enabled"]), "guides": clean_guides}


class ConnectionGuideStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._data = empty_guide_data()
        self.load()

    def load(self) -> None:
        if not self.path.is_file():
            self._data = empty_guide_data()
            return
        try:
            self._data = validate_guide_data(json.loads(self.path.read_text(encoding="utf-8")))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError):
            self._data = empty_guide_data()

    @property
    def enabled(self) -> bool:
        return bool(self._data["enabled"])

    def list_guides(self) -> list[dict[str, Any]]:
        return [dict(guide, messages=[dict(message) for message in guide["messages"]]) for guide in self._data["guides"]]

    def get(self, guide_id: str) -> dict[str, Any] | None:
        return next((guide for guide in self.list_guides() if guide["id"] == guide_id), None)

    def set_enabled(self, enabled: bool) -> None:
        if enabled and not self._data["guides"]:
            raise ValueError("add at least one connection guide before enabling the feature")
        self._data["enabled"] = bool(enabled)
        self._save()

    def add(self, title: str, messages: list[dict[str, str]]) -> str:
        if len(self._data["guides"]) >= MAX_GUIDES:
            raise ValueError(f"only {MAX_GUIDES} connection guides are allowed")
        guide_id = secrets.token_hex(6)
        candidate = {
            **self._data,
            "guides": [*self._data["guides"], {"id": guide_id, "title": title, "messages": messages}],
        }
        self._data = validate_guide_data(candidate)
        self._save()
        return guide_id

    def update_title(self, guide_id: str, title: str) -> bool:
        guides = self.list_guides()
        for guide in guides:
            if guide["id"] == guide_id:
                guide["title"] = title
                self._commit_guides(guides)
                return True
        return False

    def replace_message(self, guide_id: str, index: int, message: dict[str, str]) -> bool:
        guides = self.list_guides()
        for guide in guides:
            if guide["id"] == guide_id:
                if not 0 <= index < len(guide["messages"]):
                    return False
                guide["messages"][index] = message
                self._commit_guides(guides)
                return True
        return False

    def append_message(self, guide_id: str, message: dict[str, str]) -> bool:
        guides = self.list_guides()
        for guide in guides:
            if guide["id"] == guide_id:
                if len(guide["messages"]) >= MAX_MESSAGES_PER_GUIDE:
                    raise ValueError(f"only {MAX_MESSAGES_PER_GUIDE} messages are allowed per guide")
                guide["messages"].append(message)
                self._commit_guides(guides)
                return True
        return False

    def delete_message(self, guide_id: str, index: int) -> bool:
        guides = self.list_guides()
        for guide in guides:
            if guide["id"] == guide_id:
                if len(guide["messages"]) == 1:
                    raise ValueError("a connection guide must retain at least one message")
                if not 0 <= index < len(guide["messages"]):
                    return False
                del guide["messages"][index]
                self._commit_guides(guides)
                return True
        return False

    def delete(self, guide_id: str) -> bool:
        guides = [guide for guide in self._data["guides"] if guide["id"] != guide_id]
        if len(guides) == len(self._data["guides"]):
            return False
        self._data["guides"] = guides
        if not guides:
            self._data["enabled"] = False
        self._save()
        return True

    def _commit_guides(self, guides: list[dict[str, Any]]) -> None:
        candidate = {**self._data, "guides": guides}
        self._data = validate_guide_data(candidate)
        self._save()

    def _save(self) -> None:
        self._data = validate_guide_data(self._data)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary_name = tempfile.mkstemp(prefix=f".{self.path.name}.", dir=self.path.parent, text=True)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(self._data, handle, ensure_ascii=False, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_name, self.path)
        except BaseException:
            Path(temporary_name).unlink(missing_ok=True)
            raise
