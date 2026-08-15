# SUI Bot

SUI Bot is a Telegram administration bot for an [S-UI](https://github.com/alireza0/s-ui) panel. It gives administrators a convenient Telegram interface for managing clients while letting each user view their own subscription, usage, links, and renewal options.

## Features

- Create, edit, enable, disable, and delete S-UI clients.
- Assign one or more subscriptions to a Telegram account.
- Display usage, expiry, status, subscription links, and web-panel links.
- Accept free-form group names when creating or editing clients.
- Handle renewal plans, payment receipts, approval, and rejection.
- Send broadcasts and expiry reminders.
- Create size-limited database backups and report server health.
- Export and restore bot assignments, user preferences, metrics, runtime configuration, and cached state as one validated file.
- Support English, Persian, Russian, and Chinese per Telegram account.
- Run continuously as a hardened systemd service.
- Provide a global `sui-bot` management command.

## Requirements

- A Linux server using systemd.
- Root or `sudo` access.
- A working S-UI panel and administrator API token.
- A Telegram bot token from BotFather.
- HTTPS for a remotely hosted S-UI panel.

Python, the isolated virtual environment, Python packages, and Git are installed or configured by the installer when supported by the Linux distribution.

Redis is optional and disabled by default, so a normal installation does not emit Redis connection warnings. Set `REDIS_ENABLED=true` only when a reachable Redis server has been configured.

## Install with one command

Run:

```bash
curl --proto '=https' --tlsv1.2 -fsSL https://raw.githubusercontent.com/Sownix21/SUI-Bot/main/scripts/install.sh | sudo bash
```

The installer asks for only:

1. Your S-UI panel URL, such as `https://panel.example.com`.
2. Your S-UI administrator token.
3. Your Telegram bot token.
4. Your Telegram administrator ID.

You do not need to enter a subscription URI or configure inbounds manually. On every startup, SUI Bot sends an authenticated request to:

```text
GET <SUI_HOST>/apiv2/load
Token: <SUI_TOKEN>
```

It extracts `obj.subURI` and `obj.inbounds`, caches those two values, and uses them when building subscription links and client menus. Other fields in the response—including sensitive panel configuration—are not logged or persisted.

The installer then:

- creates a restricted `sui-bot` system user;
- installs the application in `/opt/sui-bot`;
- creates a dedicated Python environment in `/opt/sui-bot/.venv`;
- stores protected credentials in `/etc/sui-bot/sui-bot.env`;
- creates the writable state directory `/var/lib/sui-bot`;
- installs and enables `sui-bot.service`;
- installs `/usr/local/bin/sui-bot` so the management menu works from any directory.

## First Telegram launch

Open the bot and send:

```text
/start
```

Every account—including the administrator—is asked to select English, Persian, Russian, or Chinese the first time it starts the bot. The language can be changed later using the Language button.

The selected language applies to the complete Telegram interface: administrator menus and workflows, user subscription and renewal screens, inline buttons, validation/errors, scheduled reminders, reports, backup notifications, and captions. Server-provided names, descriptions, IDs, commands, and URLs remain unchanged.

Users with one assigned client see **My Subscription** and go directly to it. **My Subscriptions** and the subscription-list back button are shown only to users with multiple assigned clients.

## Manage the bot

Run this command from any directory:

```bash
sudo sui-bot
```

The interactive menu can:

- show service status;
- start, stop, or restart the bot;
- display recent logs or follow live logs;
- modify credentials and operational settings;
- validate the configuration;
- diagnose assignment and state files;
- download and install the latest GitHub release;
- completely uninstall SUI Bot.

Direct commands are also available:

```bash
sui-bot status
sudo sui-bot start
sudo sui-bot stop
sudo sui-bot restart
sui-bot logs -n 200
sui-bot logs --follow
sudo sui-bot config
sui-bot show-config
sui-bot validate
sudo sui-bot doctor
sudo sui-bot update
sudo sui-bot uninstall
```

## Backup and restore bot state

Only the configured Telegram administrator can create or restore a state backup.

To create one:

1. Open **Settings** in the Telegram admin menu.
2. Select **Backup & Restore**.
3. Select **Create & Send Backup**.
4. Keep the received `.sui-backup.json` document private.

The bundle includes assignments, Telegram user language preferences, metrics, renewal/payment runtime settings, subscription and inbound caches, and expiry-notification state. It also includes a non-secret configuration summary. `BOT_TOKEN` and `SUI_TOKEN` are intentionally excluded because Telegram backup documents should not contain reusable service credentials.

To restore the bundle:

```text
/restore
```

Then send the backup document to the bot. Before replacing any managed state, SUI Bot checks the administrator ID, 10 MiB size limit, bundle version, SHA-256 checksum, allowed sections, assignment IDs, language codes, and runtime-setting keys. Restored assignments and settings are reloaded immediately. Use `/cancel` to leave restore mode without changing anything.

## Updating without losing data

For installations already using the SUI Bot paths, run:

```bash
sudo sui-bot update
```

Updates replace the application and virtual environment but preserve:

- `/etc/sui-bot/sui-bot.env`
- `/var/lib/sui-bot`
- assignments, language choices, caches, metrics, settings, and backups stored inside the state directory

You do not need to copy these files again during later SUI Bot updates.

### One-time migration from the earlier installation layout

The previous service layout used a different state directory. Installing this release does not automatically merge that directory with `/var/lib/sui-bot`. If your data is still in `/var/lib/obscura-bot`, perform this one-time migration:

```bash
sudo systemctl disable --now obscura-bot.service
sudo systemctl stop sui-bot.service
sudo cp -a /var/lib/obscura-bot/. /var/lib/sui-bot/
sudo chown -R sui-bot:sui-bot /var/lib/sui-bot
sudo chmod -R u+rwX,g+rX,o-rwx /var/lib/sui-bot
sudo systemctl restart sui-bot.service
sudo sui-bot doctor
```

Do this before creating new assignments in SUI Bot because copying the legacy directory can overwrite newer state files. Once the data is under `/var/lib/sui-bot`, future updates preserve it automatically.

## Important files and directories

| Location | Purpose |
| --- | --- |
| `/opt/sui-bot` | Installed application and virtual environment |
| `/etc/sui-bot/sui-bot.env` | Protected credentials and configuration |
| `/var/lib/sui-bot/assignments.json` | Telegram-to-S-UI client assignments |
| `/var/lib/sui-bot/backups` | Downloaded database backups |
| `/var/lib/sui-bot/user_languages.json` | Per-user language preferences |
| `/var/lib/sui-bot/runtime_settings.json` | Renewal and payment display settings |
| `/var/lib/sui-bot/subscription_cache.json` | Last valid S-UI subscription URI |
| `/var/lib/sui-bot/inbounds_cache.json` | Last valid inbound list |
| `/etc/systemd/system/sui-bot.service` | systemd service definition |
| `/usr/local/bin/sui-bot` | Global management command |

Relative data paths are resolved below `/var/lib/sui-bot` when running under systemd.

## Configuration

The required settings are:

| Setting | Description |
| --- | --- |
| `SUI_HOST` | Base URL of the S-UI panel |
| `SUI_TOKEN` | S-UI administrator API token |
| `BOT_TOKEN` | Telegram bot token |
| `ADMIN_TELEGRAM_ID` | Telegram ID allowed to use administrator functions |

Optional values are documented in [.env.example](.env.example). The easiest way to change settings after installation is:

```bash
sudo sui-bot config
```

Tokens are masked when configuration is displayed. The environment file is written atomically with mode `0600`.

Remote S-UI endpoints must use HTTPS. Plain HTTP is accepted automatically only for loopback addresses. `ALLOW_INSECURE_HTTP=true` is available for a trusted private deployment, but it should never be used across the public internet.

## Troubleshooting

Check the service and recent logs:

```bash
systemctl status sui-bot.service
journalctl -u sui-bot.service -n 200 --no-pager
```

Follow logs live:

```bash
journalctl -u sui-bot.service -f
```

Validate configuration and data locations:

```bash
sudo sui-bot validate
sudo sui-bot doctor
```

If migrated files cannot be read or written:

```bash
sudo chown -R sui-bot:sui-bot /var/lib/sui-bot
sudo chmod -R u+rwX,g+rX,o-rwx /var/lib/sui-bot
sudo systemctl restart sui-bot.service
```

If subscription links or inbounds are unavailable, verify that `SUI_HOST` is reachable and that `SUI_TOKEN` is allowed to call `/apiv2/load`.

Reminder reports identify every due subscription that is not assigned to Telegram. Each entry includes its description, S-UI username, client ID, and remaining days so the administrator can link it with `/assign`.

## Security notes

- Non-administrator callbacks are denied unless explicitly allow-listed.
- Users can access only client IDs assigned to their Telegram ID.
- Remote plain-HTTP S-UI URLs are rejected by default.
- API responses are size-limited and requested with connection/read timeouts.
- Full `/apiv2/load` responses are never logged or saved.
- Secrets remain in the protected system environment file.
- The systemd service uses a dedicated unprivileged account and filesystem hardening.
- Backup downloads are streamed with a configurable maximum size.

Never publish S-UI tokens, Telegram tokens, TLS private keys, or complete `/apiv2/load` responses.

## Uninstall

Run:

```bash
sudo sui-bot uninstall
```

You must type `UNINSTALL SUI BOT` to confirm. Uninstallation removes the application, service, configuration, system user, assignments, settings, and backups. Copy anything you want to retain before confirming.

## Local development

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
# Edit .env, then start the Telegram bot:
python -m sui_bot
```

PowerShell activation is `.venv\Scripts\Activate.ps1`.

Run the checks with:

```bash
python -m compileall -q src
ruff check src tests
pytest
```

## Repository layout

```text
.
├── .github/workflows/ci.yml
├── deploy/systemd/sui-bot.service
├── deploy/sui-bot
├── scripts/install.sh
├── src/sui_bot/
│   ├── bot.py
│   ├── cli.py
│   ├── config.py
│   ├── localization.py
│   ├── navigation.py
│   ├── security.py
│   └── sui_metadata.py
├── tests/
├── .env.example
└── pyproject.toml
```

## License

SUI Bot is distributed under the terms in [LICENSE](LICENSE).
