import json

import pytest

from sui_bot.connection_guides import ConnectionGuideStore, split_guide_text, validate_guide_data


def test_connection_guides_round_trip_and_toggle(tmp_path) -> None:
    path = tmp_path / "connection_guides.json"
    store = ConnectionGuideStore(path)

    with pytest.raises(ValueError, match="at least one"):
        store.set_enabled(True)

    guide_id = store.add("Android", [
        {"type": "text", "text": "Install the recommended app."},
        {"type": "video", "file_id": "telegram-file-id", "caption": "Setup video"},
    ])
    store.set_enabled(True)

    reloaded = ConnectionGuideStore(path)
    assert reloaded.enabled
    assert reloaded.get(guide_id)["title"] == "Android"
    assert len(reloaded.get(guide_id)["messages"]) == 2
    assert json.loads(path.read_text(encoding="utf-8"))["version"] == 1

    assert reloaded.delete(guide_id)
    assert not reloaded.enabled


def test_connection_guide_validation_rejects_unknown_fields() -> None:
    with pytest.raises(ValueError, match="unsupported fields"):
        validate_guide_data({
            "version": 1,
            "enabled": True,
            "guides": [{
                "id": "abcdef123456",
                "title": "iOS",
                "messages": [{"type": "text", "text": "Hello", "unsafe": True}],
            }],
        })


def test_connection_guide_items_can_be_edited_without_recreating_guide(tmp_path) -> None:
    store = ConnectionGuideStore(tmp_path / "connection_guides.json")
    guide_id = store.add("Android", [{"type": "text", "text": "Old app"}])

    assert store.update_title(guide_id, "Android & TV")
    assert store.replace_message(guide_id, 0, {"type": "text", "text": "New app"})
    assert store.append_message(guide_id, {"type": "video", "file_id": "new-video", "caption": "Watch"})
    assert store.delete_message(guide_id, 0)

    guide = ConnectionGuideStore(store.path).get(guide_id)
    assert guide["title"] == "Android & TV"
    assert guide["messages"] == [{"type": "video", "file_id": "new-video", "caption": "Watch"}]
    with pytest.raises(ValueError, match="retain at least one"):
        store.delete_message(guide_id, 0)


def test_long_guide_text_is_split_losslessly_for_telegram() -> None:
    text = ("first line\n" * 500) + ("x" * 4096) + "\nlast"
    chunks = split_guide_text(text)
    assert "".join(chunks) == text
    assert all(1 <= len(chunk) <= 4096 for chunk in chunks)
    boundary_chunks = split_guide_text(("x" * 4096) + "\nlast")
    assert "".join(boundary_chunks) == ("x" * 4096) + "\nlast"
    assert all(len(chunk) <= 4096 for chunk in boundary_chunks)
