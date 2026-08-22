"""Bounded, asynchronous backup streaming."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Protocol


class AsyncReadable(Protocol):
    @property
    def content(self): ...


class BackupTooLargeError(RuntimeError):
    pass


SQLITE_HEADER = b"SQLite format 3\x00"


def validate_sqlite_database(path: Path) -> None:
    """Reject and remove downloads that are not SQLite 3 database files."""
    try:
        with path.open("rb") as handle:
            header = handle.read(len(SQLITE_HEADER))
    except OSError:
        path.unlink(missing_ok=True)
        raise
    if header != SQLITE_HEADER:
        path.unlink(missing_ok=True)
        raise RuntimeError("S-UI backup response is not a valid SQLite database")


async def stream_response_to_file(response: AsyncReadable, destination: Path, max_bytes: int) -> int:
    """Stream a response to disk and reject it before it exceeds ``max_bytes``."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    try:
        with destination.open("wb") as handle:
            async for chunk in response.content.iter_chunked(64 * 1024):
                written += len(chunk)
                if written > max_bytes:
                    raise BackupTooLargeError(f"Backup exceeds {max_bytes} bytes")
                await asyncio.to_thread(handle.write, chunk)
    except BaseException:
        await asyncio.to_thread(destination.unlink, missing_ok=True)
        raise
    if written == 0:
        await asyncio.to_thread(destination.unlink, missing_ok=True)
        raise RuntimeError("Received empty database file")
    return written
