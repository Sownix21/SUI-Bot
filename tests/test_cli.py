import os
from pathlib import Path

import pytest

from sui_bot import cli


def valid_environment() -> dict[str, str]:
    return {
        "SUI_HOST": "https://panel.example.com",
        "SUI_TOKEN": "sui-secret",
        "BOT_TOKEN": "123456:abcdefghijklmnopqrstuvwxyz_ABCD",
        "ADMIN_TELEGRAM_ID": "123456",
        "ALLOW_INSECURE_HTTP": "false",
    }


def test_validation_accepts_secure_configuration() -> None:
    assert cli.validate_environment(valid_environment()) == []


def test_validation_rejects_remote_plain_http() -> None:
    values = valid_environment()
    values["SUI_HOST"] = "http://panel.example.com"
    assert any("HTTPS" in error for error in cli.validate_environment(values))


def test_validation_rejects_invalid_token_and_runtime_bounds() -> None:
    values = valid_environment()
    values.update({"BOT_TOKEN": "not-a-token", "ITEMS_PER_PAGE": "0", "REDIS_PORT": "70000"})
    errors = cli.validate_environment(values)
    assert any("BOT_TOKEN" in error for error in errors)
    assert any("ITEMS_PER_PAGE" in error for error in errors)
    assert any("REDIS_PORT" in error for error in errors)


def test_validation_rejects_public_subscription_origin_with_path() -> None:
    values = valid_environment()
    values["SUBSCRIPTION_PUBLIC_ORIGIN"] = "https://example.com/not-an-origin"
    assert any("must not contain a path" in error for error in cli.validate_environment(values))


def test_validation_rejects_state_path_traversal() -> None:
    values = valid_environment()
    values["BACKUP_DIR"] = "../../outside"
    assert any("BACKUP_DIR" in error for error in cli.validate_environment(values))


def test_secret_masking() -> None:
    assert cli.mask_value("BOT_TOKEN", "abcdefgh") == "••••••••efgh"
    assert cli.mask_value("ADMIN_TELEGRAM_ID", "123") == "123"


def test_relative_data_paths_resolve_under_state_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli, "STATE_DIR", tmp_path)
    assert cli.configured_data_path({}, "ASSIGNMENTS_FILE", "assignments.json") == tmp_path / "assignments.json"
    absolute = tmp_path / "custom.json"
    assert cli.configured_data_path({"ASSIGNMENTS_FILE": str(absolute)}, "ASSIGNMENTS_FILE", "assignments.json") == absolute


def test_atomic_environment_write_is_reloadable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = tmp_path / "sui-bot.env"
    monkeypatch.setattr(cli, "require_root", lambda _action: None)
    cli.write_environment(valid_environment(), target)
    assert cli.load_environment(target) == valid_environment()
    if os.name == "posix":
        assert target.stat().st_mode & 0o777 == 0o600


def test_uninstall_removes_only_managed_components(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    install_dir = tmp_path / "opt" / "sui-bot"
    config_dir = tmp_path / "etc" / "sui-bot"
    state_dir = tmp_path / "var" / "lib" / "sui-bot"
    service_file = tmp_path / "etc" / "systemd" / "sui-bot.service"
    command_file = tmp_path / "usr" / "local" / "bin" / "sui-bot"
    for directory in (install_dir, config_dir, state_dir):
        directory.mkdir(parents=True)
        (directory / "managed-data").write_text("test", encoding="utf-8")
    for file in (service_file, command_file):
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text("test", encoding="utf-8")

    calls: list[list[str]] = []
    monkeypatch.setattr(cli, "INSTALL_DIR", install_dir)
    monkeypatch.setattr(cli, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(cli, "STATE_DIR", state_dir)
    monkeypatch.setattr(cli, "SERVICE_FILE", service_file)
    monkeypatch.setattr(cli, "COMMAND_FILE", command_file)
    monkeypatch.setattr(cli, "require_root", lambda _action: None)
    monkeypatch.setattr(cli, "require_command", lambda _command: "/bin/systemctl")
    monkeypatch.setattr(cli.shutil, "which", lambda _command: None)
    monkeypatch.setattr(cli.subprocess, "run", lambda command, **_kwargs: calls.append(command))

    cli.uninstall_bot(confirmed=True)

    assert not install_dir.exists()
    assert not config_dir.exists()
    assert not state_dir.exists()
    assert not service_file.exists()
    assert not command_file.exists()
    assert ["/bin/systemctl", "daemon-reload"] in calls
