import json

import pytest

from sui_bot.backup_bundle import build_bundle, load_bundle, restore_bundle, write_bundle


def test_bundle_round_trip_restores_allowlisted_state(tmp_path):
    assignments = tmp_path / "assignments.json"
    metrics = tmp_path / "metrics.json"
    assignments.write_text('{"100": [1, 2]}', encoding="utf-8")
    metrics.write_text('{"total_commands": 5}', encoding="utf-8")
    paths = {"assignments": assignments, "metrics": metrics}
    bundle_path = tmp_path / "backup.sui-backup.json"

    bundle = build_bundle(paths, {"admin_telegram_id": 100, "secrets_included": False})
    write_bundle(bundle, bundle_path)
    assignments.write_text("{}", encoding="utf-8")
    restored = restore_bundle(load_bundle(bundle_path), paths)

    assert restored == ["assignments", "metrics"]
    assert json.loads(assignments.read_text(encoding="utf-8")) == {"100": [1, 2]}


def test_modified_bundle_is_rejected(tmp_path):
    source = tmp_path / "assignments.json"
    source.write_text('{"100": [1]}', encoding="utf-8")
    path = tmp_path / "backup.json"
    bundle = build_bundle({"assignments": source}, {})
    bundle["state"]["assignments"]["100"] = [999]
    path.write_text(json.dumps(bundle), encoding="utf-8")

    with pytest.raises(ValueError, match="checksum"):
        load_bundle(path)


def test_unknown_state_file_is_rejected(tmp_path):
    source = tmp_path / "unknown.json"
    source.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="unsupported"):
        build_bundle({"unknown": source}, {})


def test_invalid_assignment_schema_is_rejected(tmp_path):
    source = tmp_path / "assignments.json"
    source.write_text('{"100": [0, "bad"]}', encoding="utf-8")
    with pytest.raises(ValueError, match="invalid Telegram or client ID"):
        build_bundle({"assignments": source}, {})
