import os
import subprocess
import sys


def test_invalid_configuration_exits_once_without_traceback(tmp_path) -> None:
    environment = os.environ.copy()
    environment.update({
        "SUI_HOST": "https://panel.example.com",
        "SUI_TOKEN": "secret",
        "BOT_TOKEN": "123456:abcdefghijklmnopqrstuvwxyz_ABCD",
        "ADMIN_TELEGRAM_ID": "123456",
        "ITEMS_PER_PAGE": "0",
        "DATA_DIR": str(tmp_path),
        "BOT_LOG_FILE": "",
    })
    result = subprocess.run(  # noqa: S603 - current test interpreter and fixed module
        [sys.executable, "-m", "sui_bot"],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 78
    assert "SUI Bot configuration error" in result.stderr
    assert "Traceback" not in result.stderr
