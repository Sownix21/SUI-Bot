from pathlib import Path

import pytest

from sui_bot.backup import (
    SQLITE_HEADER,
    BackupTooLargeError,
    stream_response_to_file,
    validate_sqlite_database,
)


class Content:
    def __init__(self, chunks: list[bytes]):
        self.chunks = chunks

    async def iter_chunked(self, _size: int):
        for chunk in self.chunks:
            yield chunk


class Response:
    def __init__(self, chunks: list[bytes]):
        self.content = Content(chunks)


async def test_streams_backup_within_limit(tmp_path: Path) -> None:
    destination = tmp_path / "backup.db"
    written = await stream_response_to_file(Response([b"abc", b"def"]), destination, 6)
    assert written == 6
    assert destination.read_bytes() == b"abcdef"


async def test_removes_partial_backup_above_limit(tmp_path: Path) -> None:
    destination = tmp_path / "backup.db"
    with pytest.raises(BackupTooLargeError):
        await stream_response_to_file(Response([b"1234", b"5678"]), destination, 7)
    assert not destination.exists()


def test_accepts_sqlite_database_header(tmp_path: Path) -> None:
    destination = tmp_path / "backup.db"
    destination.write_bytes(SQLITE_HEADER + bytes(256))
    validate_sqlite_database(destination)
    assert destination.exists()


def test_rejects_and_removes_json_error_download(tmp_path: Path) -> None:
    destination = tmp_path / "backup.db"
    destination.write_bytes(b'{"success":false,"msg":"request failed","obj":null}')
    with pytest.raises(RuntimeError, match="not a valid SQLite database"):
        validate_sqlite_database(destination)
    assert not destination.exists()
