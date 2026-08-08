from pathlib import Path

import pytest

from obscura_bot.backup import BackupTooLargeError, stream_response_to_file


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

