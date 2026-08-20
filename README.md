# SUI Bot

[English](README.md) | [فارسی](README.fa.md)

SUI Bot is a Telegram administration bot for an [S-UI](https://github.com/alireza0/s-ui) panel. It gives administrators a convenient Telegram interface for managing clients while letting each user view their own subscription, usage, links, and renewal options.

## Features

- Create, edit, enable, disable, and delete S-UI clients.
- Assign one or more subscriptions to a Telegram account.
- Display usage, expiry, status, subscription links, and web-panel links.
- Handle renewal plans, payment receipts, approval, and rejection.
- Send broadcasts and expiry reminders.
- Let administrators publish ordered, media-rich connection guides for Android, iOS, Windows, or custom platforms.
- Create size-limited database backups and report server health.
- Export and restore bot assignments, user preferences, metrics, runtime configuration, and cached state as one validated file.
- Support English, Persian, Russian, and Chinese per Telegram account.
- Let each owner customize the name used inside bot messages .
- Optionally hide the explicit port in user-facing subscription links .
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

The selected language applies to the complete Telegram interface: administrator menus and workflows, user subscription and renewal screens, inline buttons, validation/errors, scheduled reminders, reports, backup notifications, and captions. Server-provided names, descriptions, IDs, and commands remain unchanged. URLs also remain unchanged unless the administrator explicitly enables the subscription-port removal option described below.

The administrator can change the owner-facing brand from **Settings → Set message display name**. This changes only the name written inside messages produced by the bot. It never changes the Telegram profile name or `@username`; those remain exactly as configured through BotFather. Linux service names and data paths also remain `sui-bot`.

The admin-only **Remove port from subscription links** setting can produce clean user-facing URLs such as `https://example.com/path/user/` instead of `https://example.com:2096/path/user/`. Enabling it requires a separate confirmation after a warning. Configure nginx, another reverse proxy, or equivalent server routing first so portless requests reach the S-UI subscription endpoint; otherwise the rewritten links will fail. The bot does not modify nginx or the S-UI server.

Expiry reminders include direct renewal actions. The final-day reminder says **24 hours remaining** rather than one day. When an assigned subscription expires, its Telegram user receives a localized expiration message with the appropriate renewal button; the administrator still receives the separate expiration report. A single expiring subscription gets one renewal action, while messages containing several subscriptions provide a separate action for each subscription.

### Connection guides

The administrator can open **Settings → Connection Guides** to:

1. Add Android, iOS, Windows, macOS, Linux, or any custom option.
2. Send up to 30 text messages, photos, videos, or documents in the exact order users should receive them. Media captions are retained.
3. Send `/done` to save the guide, then enable the feature.
4. Disable the user button or delete individual guides later.

When enabled, users see a localized **Connection Guide** button in the main menu. Guide titles and administrator-authored content are intentionally delivered exactly as entered. Guide configuration and reusable Telegram media IDs are stored in `/var/lib/sui-bot/connection_guides.json` and included in SUI Bot state backups.

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
sudo sui-bot web-panel
sudo sui-bot remove-web-panel
sudo sui-bot uninstall
```

## Optional web panel and clean-link proxy

The regular SUI Bot install and update commands do **not** install nginx, request a certificate, or publish this panel. They only include the inactive template. Web setup starts only when the owner explicitly selects the web-panel menu option or runs the command below.

Run `sudo sui-bot` and choose **Install/update web panel and nginx proxy**, or run `sudo sui-bot web-panel`. The setup uses the bundled dashboard based on the supplied owner design, but generates every server-specific value at installation time. It:

- reads the current S-UI subscription path and private port from `/var/lib/sui-bot/subscription_cache.json`;
- asks for the public domain, dashboard title, a private dashboard route, and a dedicated dashboard HTTPS port (default `2083`);
- installs nginx and Certbot through `apt`, `dnf`, or `yum` when approved and missing;
- obtains or reuses a Let's Encrypt certificate;
- writes only `/etc/nginx/conf.d/sui-bot-web-panel.conf`—it never overwrites nginx's `default` site;
- keeps the listeners separate: clean subscription links use public HTTPS `443`, the dashboard uses its selected port such as `2083`, and nginx proxies subscriptions internally to the detected S-UI port such as `2096`;
- renders the dashboard without embedding a VPS IP, S-UI token, fixed domain, fixed port, or fixed subscription path;
- runs `nginx -t` before every reload and restores the previous managed configuration if setup fails;
- configures the bot's Web Panel button and restarts SUI Bot.

The dashboard port must differ from ports `80`, `443`, and the S-UI subscription port, and it must not already be occupied by another service or nginx site. The installer explains this requirement and checks the selected port before making changes. Automatic setup is portable across systemd VPSs using the supported package managers when S-UI is on the same VPS. It still cannot create DNS records or open provider firewalls: before running it, point a dedicated domain to the VPS and allow inbound TCP 80, 443, and the selected dashboard port. If another nginx site already owns that domain, setup refuses to continue rather than modifying unrelated configuration. Remove only the managed panel with `sudo sui-bot remove-web-panel`; certificates and shared nginx packages are retained for safety.

The dashboard title follows the current **message display name** configured in Telegram Settings whenever a user opens a newly generated Web Panel link. This still does not change the bot's BotFather profile name or `@username`. A previously sent Telegram message may contain the earlier title; reopening the bot menu generates a fresh link.

The administrator must separately enable **Settings → Enable Web Panel** in Telegram. A localized warning explains that this toggle does not install nginx, certificates, or firewall rules and that `sudo sui-bot web-panel` must be completed on Linux. The preference may be enabled before installation, but the user button remains hidden until both the toggle is enabled and the Linux installer has configured a valid panel URL. Removing the panel from Linux also disables the Telegram toggle.

## Backup and restore bot state

Only the configured Telegram administrator can create or restore a state backup.

To create one:

1. Open **Settings** in the Telegram admin menu.
2. Select **Backup & Restore**.
3. Select **Create & Send Backup**.
4. Keep the received `.sui-backup.json` document private.

The bundle includes assignments, Telegram user language preferences, connection guides, metrics, renewal/payment runtime settings, subscription and inbound caches, and expiry-notification state. It also includes a non-secret configuration summary. `BOT_TOKEN` and `SUI_TOKEN` are intentionally excluded because Telegram backup documents should not contain reusable service credentials.

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

## Important files and directories

| Location | Purpose |
| --- | --- |
| `/opt/sui-bot` | Installed application and virtual environment |
| `/etc/sui-bot/sui-bot.env` | Protected credentials and configuration |
| `/var/lib/sui-bot/assignments.json` | Telegram-to-S-UI client assignments |
| `/var/lib/sui-bot/backups` | Downloaded database backups |
| `/var/lib/sui-bot/user_languages.json` | Per-user language preferences |
| `/var/lib/sui-bot/runtime_settings.json` | Renewal and payment display settings |
| `/var/lib/sui-bot/connection_guides.json` | Enabled state and administrator-authored connection guides |
| `/var/www/sui-bot/index.html` | Generated optional web-panel page |
| `/etc/nginx/conf.d/sui-bot-web-panel.conf` | Optional nginx site managed by `sui-bot web-panel` |
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
