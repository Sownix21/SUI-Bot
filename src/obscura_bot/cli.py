"""Linux administration CLI for the SUI Bot service."""

from __future__ import annotations

import argparse
import getpass
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import dotenv_values

from .security import validate_service_url

SERVICE_NAME = "obscura-bot.service"
DEFAULT_ENV_FILE = Path("/etc/obscura-bot/obscura-bot.env")
SERVICE_FILE = Path("/etc/systemd/system/obscura-bot.service")
INSTALL_DIR = Path("/opt/obscura-bot")
CONFIG_DIR = Path("/etc/obscura-bot")
STATE_DIR = Path("/var/lib/obscura-bot")
COMMAND_FILE = Path("/usr/local/bin/sui-bot")
SERVICE_USER = "obscura-bot"
SECRET_KEYS = {"BOT_TOKEN", "SUI_TOKEN"}
REQUIRED_KEYS = {"SUI_HOST", "SUI_TOKEN", "BOT_TOKEN", "ADMIN_TELEGRAM_ID", "FALLBACK_SUB_URI"}
EDITABLE_FIELDS = [
    ("SUI_HOST", "S-UI URL"),
    ("SUI_TOKEN", "S-UI token"),
    ("BOT_TOKEN", "Telegram bot token"),
    ("ADMIN_TELEGRAM_ID", "Admin Telegram ID"),
    ("FALLBACK_SUB_URI", "Fallback subscription URL"),
    ("ADMIN_CLIENT_ID", "Admin client ID"),
    ("ALLOW_INSECURE_HTTP", "Allow insecure HTTP"),
    ("REDIS_HOST", "Redis host"),
    ("REDIS_PORT", "Redis port"),
    ("REDIS_DB", "Redis database"),
    ("BACKUP_DIR", "Backup directory"),
    ("BACKUP_MAX_BYTES", "Maximum backup bytes"),
    ("RENEWAL_MONTHLY_PRICE", "Monthly renewal price"),
    ("RENEWAL_MONTH_OPTIONS", "Renewal month options"),
    ("PAYMENT_CARD_NUMBER", "Payment card number"),
    ("PAYMENT_CARD_HOLDER", "Payment card holder"),
]


def env_file() -> Path:
    return Path(os.getenv("OBSCURA_SYSTEM_ENV_FILE", str(DEFAULT_ENV_FILE)))


def require_root(action: str) -> None:
    geteuid = getattr(os, "geteuid", None)
    if geteuid is None or geteuid() != 0:
        raise PermissionError(f"{action} requires root privileges. Run: sudo sui-bot")


def require_command(command: str) -> str:
    resolved = shutil.which(command)
    if resolved is None:
        raise RuntimeError(f"Required command not found: {command}")
    return resolved


def systemctl(action: str, *, check: bool = False) -> int:
    allowed_actions = {"status", "start", "stop", "restart", "enable", "disable"}
    if action not in allowed_actions:
        raise ValueError(f"Unsupported systemctl action: {action}")
    executable = require_command("systemctl")
    if action in {"start", "stop", "restart", "enable", "disable"}:
        require_root(f"systemctl {action}")
    result = subprocess.run([executable, action, SERVICE_NAME], check=check)  # noqa: S603 - fixed executable and allow-listed action
    return result.returncode


def show_logs(*, follow: bool = False, lines: int = 100) -> int:
    executable = require_command("journalctl")
    command = [executable, "--unit", SERVICE_NAME, "--no-pager", "--lines", str(max(1, lines))]
    if follow:
        command.extend(["--follow", "--output", "cat"])
    try:
        return subprocess.run(command, check=False).returncode  # noqa: S603 - fixed executable and constructed arguments
    except KeyboardInterrupt:
        return 130


def load_environment(path: Path | None = None) -> dict[str, str]:
    source = path or env_file()
    if not source.is_file():
        raise FileNotFoundError(f"Configuration file not found: {source}")
    return {key: "" if value is None else str(value) for key, value in dotenv_values(source).items()}


def _quoted(value: str) -> str:
    if "\n" in value or "\r" in value:
        raise ValueError("Environment values cannot contain newlines")
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def write_environment(values: dict[str, str], path: Path | None = None) -> None:
    require_root("Editing bot configuration")
    destination = path or env_file()
    destination.parent.mkdir(parents=True, exist_ok=True)
    ordered_keys = [key for key, _ in EDITABLE_FIELDS if key in values]
    ordered_keys.extend(sorted(set(values) - set(ordered_keys)))
    fd, temporary_name = tempfile.mkstemp(prefix=f".{destination.name}.", dir=destination.parent, text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            for key in ordered_keys:
                handle.write(f"{key}={_quoted(str(values[key]))}\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary_name, 0o600)
        os.replace(temporary_name, destination)
        os.chmod(destination, 0o600)
    except BaseException:
        Path(temporary_name).unlink(missing_ok=True)
        raise


def _bool_value(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off", ""}:
        return False
    raise ValueError("ALLOW_INSECURE_HTTP must be true or false")


def validate_environment(values: dict[str, str]) -> list[str]:
    errors = [f"Missing required value: {key}" for key in sorted(REQUIRED_KEYS) if not values.get(key, "").strip()]
    try:
        admin_id = int(values.get("ADMIN_TELEGRAM_ID", "0"))
        if admin_id <= 0:
            raise ValueError
    except ValueError:
        errors.append("ADMIN_TELEGRAM_ID must be a positive integer")
    try:
        allow_http = _bool_value(values.get("ALLOW_INSECURE_HTTP", "false"))
        if values.get("SUI_HOST"):
            validate_service_url(values["SUI_HOST"], allow_insecure_http=allow_http)
    except (RuntimeError, ValueError) as exc:
        errors.append(str(exc))
    fallback = values.get("FALLBACK_SUB_URI", "")
    if fallback:
        parsed = urlsplit(fallback)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            errors.append("FALLBACK_SUB_URI must be an absolute HTTP(S) URL")
    for key in ("ADMIN_CLIENT_ID", "REDIS_PORT", "REDIS_DB", "BACKUP_MAX_BYTES", "RENEWAL_MONTHLY_PRICE"):
        if values.get(key):
            try:
                if int(values[key]) < 0:
                    raise ValueError
            except ValueError:
                errors.append(f"{key} must be a non-negative integer")
    return errors


def mask_value(key: str, value: str) -> str:
    if key not in SECRET_KEYS:
        return value
    if not value:
        return "<not set>"
    return "•" * 8 + (value[-4:] if len(value) > 4 else "")


def show_configuration() -> None:
    values = load_environment()
    print(f"\nConfiguration: {env_file()}\n")
    for key, label in EDITABLE_FIELDS:
        print(f"{label:28} {mask_value(key, values.get(key, '<default>'))}")


def validate_configuration() -> bool:
    errors = validate_environment(load_environment())
    if errors:
        print("Configuration errors:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return False
    print("Configuration is valid.")
    return True


def edit_configuration() -> None:
    require_root("Editing bot configuration")
    values = load_environment()
    while True:
        print("\nEditable settings (tokens are never displayed):")
        for index, (key, label) in enumerate(EDITABLE_FIELDS, 1):
            print(f"  {index:2}. {label:28} {mask_value(key, values.get(key, '<default>'))}")
        print("   0. Save and return")
        choice = input("Select a setting: ").strip()
        if choice == "0":
            errors = validate_environment(values)
            if errors:
                print("Cannot save yet:")
                for error in errors:
                    print(f"  - {error}")
                continue
            write_environment(values)
            print(f"Saved {env_file()} with mode 0600.")
            if input("Restart the bot now? [Y/n]: ").strip().lower() not in {"n", "no"}:
                systemctl("restart")
            return
        try:
            key, label = EDITABLE_FIELDS[int(choice) - 1]
        except (ValueError, IndexError):
            print("Invalid selection.")
            continue
        prompt = f"New {label} (blank keeps current; '-' clears optional values): "
        new_value = getpass.getpass(prompt) if key in SECRET_KEYS else input(prompt)
        if new_value == "":
            continue
        if new_value == "-" and key not in REQUIRED_KEYS:
            new_value = ""
        values[key] = new_value


def status_summary() -> str:
    executable = shutil.which("systemctl")
    if executable is None:
        return "systemd unavailable"
    result = subprocess.run(  # noqa: S603 - fixed executable and constant arguments
        [executable, "is-active", SERVICE_NAME],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() or "unknown"


def uninstall_bot(*, confirmed: bool = False) -> None:
    """Completely remove SUI Bot after an explicit confirmation."""
    require_root("Uninstalling SUI Bot")
    if not confirmed:
        print("\nWARNING: This permanently removes SUI Bot and all of its local data, including:")
        print(f"  - Application:   {INSTALL_DIR}")
        print(f"  - Configuration: {CONFIG_DIR}")
        print(f"  - State/backups: {STATE_DIR}")
        print(f"  - Service:       {SERVICE_FILE}")
        print(f"  - Command:       {COMMAND_FILE}")
        print(f"  - System user:   {SERVICE_USER}")
        confirmation = input("\nType UNINSTALL SUI BOT to continue: ").strip()
        if confirmation != "UNINSTALL SUI BOT":
            print("Uninstallation cancelled.")
            return

    systemctl_executable = require_command("systemctl")
    subprocess.run([systemctl_executable, "stop", SERVICE_NAME], check=False)  # noqa: S603
    subprocess.run([systemctl_executable, "disable", SERVICE_NAME], check=False)  # noqa: S603
    subprocess.run([systemctl_executable, "reset-failed", SERVICE_NAME], check=False)  # noqa: S603

    SERVICE_FILE.unlink(missing_ok=True)
    COMMAND_FILE.unlink(missing_ok=True)
    for directory in (INSTALL_DIR, CONFIG_DIR, STATE_DIR):
        if directory.is_symlink():
            directory.unlink()
        elif directory.exists():
            shutil.rmtree(directory)

    subprocess.run([systemctl_executable, "daemon-reload"], check=False)  # noqa: S603

    userdel = shutil.which("userdel")
    if userdel:
        subprocess.run([userdel, SERVICE_USER], check=False)  # noqa: S603
    groupdel = shutil.which("groupdel")
    if groupdel:
        subprocess.run([groupdel, SERVICE_USER], check=False)  # noqa: S603

    print("\nSUI Bot and all managed components were completely uninstalled.")


def interactive_menu() -> int:
    actions = {
        "1": lambda: systemctl("status"),
        "2": lambda: systemctl("start"),
        "3": lambda: systemctl("stop"),
        "4": lambda: systemctl("restart"),
        "5": lambda: show_logs(follow=True),
        "6": lambda: show_logs(follow=False, lines=100),
        "7": edit_configuration,
        "8": show_configuration,
        "9": validate_configuration,
        "10": uninstall_bot,
    }
    while True:
        print("\n╭──────────────────────────────────────╮")
        print("│          SUI Bot Administration      │")
        print("╰──────────────────────────────────────╯")
        print(f"Service status: {status_summary()}\n")
        print("  1. Detailed status")
        print("  2. Start bot")
        print("  3. Stop bot")
        print("  4. Restart bot")
        print("  5. Follow live logs")
        print("  6. Show recent logs")
        print("  7. Modify credentials/settings")
        print("  8. Show configuration (secrets masked)")
        print("  9. Validate configuration")
        print(" 10. Completely uninstall SUI Bot")
        print("  0. Exit")
        choice = input("\nSelect an option: ").strip()
        if choice == "0":
            return 0
        action = actions.get(choice)
        if action is None:
            print("Invalid selection.")
            continue
        try:
            action()
        except (FileNotFoundError, PermissionError, RuntimeError, ValueError) as exc:
            print(f"Error: {exc}", file=sys.stderr)
        input("\nPress Enter to return to the menu...")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sui-bot", description="Manage the SUI Bot systemd service")
    subparsers = parser.add_subparsers(dest="command")
    for command in ("status", "start", "stop", "restart"):
        subparsers.add_parser(command)
    logs = subparsers.add_parser("logs")
    logs.add_argument("-f", "--follow", action="store_true")
    logs.add_argument("-n", "--lines", type=int, default=100)
    subparsers.add_parser("config", help="Interactively edit credentials and settings")
    subparsers.add_parser("show-config", help="Display configuration with secrets masked")
    subparsers.add_parser("validate", help="Validate the environment file")
    subparsers.add_parser("uninstall", help="Completely uninstall SUI Bot and its managed data")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command is None:
            return interactive_menu()
        if args.command in {"status", "start", "stop", "restart"}:
            return systemctl(args.command)
        if args.command == "logs":
            return show_logs(follow=args.follow, lines=max(1, args.lines))
        if args.command == "config":
            edit_configuration()
            return 0
        if args.command == "show-config":
            show_configuration()
            return 0
        if args.command == "validate":
            return 0 if validate_configuration() else 1
        if args.command == "uninstall":
            uninstall_bot()
            return 0
    except (FileNotFoundError, PermissionError, RuntimeError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 2


def run() -> None:
    raise SystemExit(main())


if __name__ == "__main__":
    run()
