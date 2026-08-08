# Obscura Bot

Obscura Bot is an asynchronous Telegram administration bot for an S-UI panel. It manages clients, assignments, usage, renewal receipts, reminders, broadcasts, backups, and server-health alerts.

## One-command Linux installation

On a systemd-based Linux server with Python 3.10 or newer:

```bash
sudo bash https://github.com/Sownix21/SUI-Bot/main/scripts/install.sh
```

The installer:

- creates the restricted `obscura-bot` system account;
- installs the project and every Python dependency into `/opt/obscura-bot/.venv`;
- interactively creates `/etc/obscura-bot/obscura-bot.env` with mode `0600`;
- installs and hardens `obscura-bot.service`;
- runs `systemctl enable --now obscura-bot`.

Check it with:

```bash
systemctl status obscura-bot
journalctl -u obscura-bot -f
```

After installation, run this from any directory to open the management menu:

```bash
sudo sui-bot
```

The menu can start, stop or restart the service, show status and live/recent logs, validate configuration, display masked settings, and securely update tokens, administrator IDs, URLs, Redis values, backup limits, and renewal settings. Credential changes are written atomically with mode `0600`, and the menu offers to restart the service afterward.

Non-interactive commands are also available:

```bash
sudo sui-bot restart
sui-bot status
sui-bot logs -n 200
sui-bot logs --follow
sudo sui-bot config
sui-bot show-config
sui-bot validate
```

For unattended installation, place a completed environment file at `/etc/obscura-bot/obscura-bot.env` before running the installer. If no terminal is available, the installer creates a protected template and exits so secrets are never guessed or placed on a command line.

## Local development

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
# Edit .env, then:
obscura-bot
```

PowerShell activation is `.venv\Scripts\Activate.ps1`. Never commit `.env`; it is ignored by Git.

Run checks with:

```bash
pytest
python -m compileall -q src
```

## Configuration

Required values are `SUI_HOST`, `SUI_TOKEN`, `BOT_TOKEN`, `ADMIN_TELEGRAM_ID`, and `FALLBACK_SUB_URI`. See [.env.example](.env.example) for optional settings.

Remote S-UI endpoints must use HTTPS. Plain HTTP is accepted automatically for loopback addresses only. `ALLOW_INSECURE_HTTP=true` is an explicit escape hatch for a trusted private network and should not be used over the public internet.

The bot never persists tokens. Admin-adjustable prices, plans, and payment display details are stored separately in `runtime_settings.json`; its allow-list rejects secret keys.

## Repository layout

```text
.
├── .github/workflows/ci.yml       GitHub Actions test matrix
├── deploy/systemd/                hardened service definition
├── scripts/install.sh             idempotent Linux installer
├── src/obscura_bot/
│   ├── bot.py                     Telegram handlers and lifecycle
│   ├── config.py                  environment configuration
│   ├── security.py                authorization and TLS policy
│   ├── cli.py                     global sui-bot management command
│   ├── backup.py                  bounded backup streaming
│   ├── reporting.py               reminder/report transforms
│   └── runtime_settings.py        non-secret mutable settings
├── tests/                          focused security and behavior tests
└── pyproject.toml                 package and dependency metadata
```

## Updating

Pull or copy a newer checkout and run `sudo bash scripts/install.sh` again. The protected environment file is preserved and the service is restarted with the newly installed package.
