# 🤖 SUI Bot

A Telegram bot for managing S-UI users, subscriptions, renewals, and subscription sales.

[فارسی](README.fa.md)

## ✨ Features

- **Subscription management:** usage, expiry, subscription links, and multiple subscriptions per Telegram account.
- **Admin tools:** create, edit, delete, and assign clients; view online users, server status, and activity reports. Interactive assignment is available alongside `/assign`.
- **Public sales:** optional storefront with admin-defined plans, prices, durations, quotas, and inbound presets. Every receipt requires admin approval; accounts can then be configured manually or created automatically and assigned to the buyer.
- **Renewals & reminders:** receipt-based renewal approval, expiry alerts with renewal buttons, and an expired-subscription notification.
- **Four languages:** English, Persian, Russian, and Chinese, selected independently by each user. Commands and server-provided content remain unchanged.
- **Personalization:** message display name, payment details, currency, administrative timezone, and editable connection guides with text, videos, images, and files. The display name does not change the bot's BotFather name or username.
- **Backups:** scheduled panel database backups and an admin-only bot backup/restore feature.
- **Linux management:** a global `sui-bot` menu for service control, logs, configuration, updates, optional web-panel setup, and uninstallation.

## 📋 Requirements

- A Linux VPS with **systemd** and root/sudo access. Ubuntu 22.04+ or Debian 12+ is a practical choice.
- Python **3.10+**, and `curl` for the installation command. The installer adds missing supported Python environment tools and dependencies.
- A working **S-UI panel**, its administrator API token, and its full URL, including any custom panel path.
- A **Telegram bot token** from BotFather and your **numeric Telegram admin ID**.
- HTTPS for a remote panel, and outbound access to Telegram, GitHub, and Python package downloads.

Redis is optional; it is not needed for a normal installation.

## 🚀 Install

```bash
curl --proto '=https' --tlsv1.2 -fsSL https://raw.githubusercontent.com/Sownix21/SUI-Bot/main/scripts/install.sh | sudo bash
```

Review the installer before running it as root. It asks for the panel URL, panel API token, Telegram bot token, and admin ID, then installs the bot in an isolated Python environment and enables its background systemd service.

Use the **full panel base URL**, for example `https://panel.example.com:2053/private-path` — do not append `/api` or `/apiv2`.

**No subscription URI is required during installation.** The bot reads it from the panel. If the panel's custom subscription URI is empty, the panel's default subscription address is used. Configure custom domains or ports in S-UI; the bot does not remove or rewrite the subscription port.

Open the bot in Telegram, send `/start`, and select your language. The configured administrator will see the management options.

## 🛒 Set up public sales

Open **Settings → Public sales**. Sales are **off by default**.

1. Configure your payment card, holder, and currency in payment settings.
2. Add a plan: title, price, duration in days, traffic allowance, and optional group, description, and remark. A duration of 30 days means exactly 30 days, not a calendar month. A zero traffic allowance means unlimited.
3. Choose whether validity starts at creation or after first VPN traffic. Optional periodic usage resets are available for plans starting at creation.
4. Choose the account creation mode:
   - **Automatic:** select an inbound preset for each active plan. After you approve a receipt, the bot generates credentials, creates the account, and assigns it to the buyer.
   - **Manual:** after approval, enter the account name and optional details, select its inbounds, and confirm creation. The purchased duration, quota, and price remain fixed.
5. Enable sales. Anyone can start the bot and choose **Buy subscription**.

Buyers submit receipt images in a private chat. Review them using the approval buttons or **Orders needing attention**. Plans can be edited or hidden without changing existing orders. Each buyer can have one open order at a time; orders survive bot restarts. Receipt verification and any refunds remain the administrator's responsibility.

Sale plans and renewal pricing are separate. Configure renewal prices and durations in payment settings as well.

If creation cannot be confirmed, use **Check creation** in the order. The bot will not blindly create another account. If it remains unresolved, check S-UI and coordinate with the buyer before taking further action.

## ⏳ Expiry, resets & renewals

- **Standard expiry:** validity starts at account creation.
- **Delayed expiry:** validity starts after the panel records the first VPN traffic, not merely when the user opens Telegram. The panel does not allow enabling delay start on an account that already has current traffic.
- **Automatic reset:** resets the current traffic allowance every selected number of days; it does **not** extend the expiry date. When combined with delay start in the admin create/edit workflow, only the first reset cycle is delayed, not expiry.
- **Renewal approval:** extends validity and resets current usage. The latest panel retains lifetime traffic totals.

## 🧭 Connection guides & optional web panel

**Connection guides:** enable the feature in admin settings, create sections such as Android or iOS, and add the recommended apps and setup instructions. Text and media can be edited or replaced later. Your own guide content is sent exactly as written.

**Already have a working web dashboard?** Run:

```bash
sudo sui-bot web-panel-link
```

Enter its base URL before the username, such as `https://panel.example.com:2083/view`. This only connects the bot button to your existing dashboard; it does not modify nginx.

**Need a new dashboard?** Run `sudo sui-bot web-panel`. This optional installer configures nginx and a TLS certificate. It needs S-UI on the same VPS, a domain pointing to that VPS, and open TCP ports **80**, **443**, and your chosen dashboard port. The dashboard port must be **unused** and different from the subscription port — for example, dashboard `2083` and subscription `2096`. A domain already owned by another nginx site is not overwritten. If your public subscription address is behind a proxy, the detected upstream may not be the actual local listener; verify it before continuing.

Finally, enable **Web Panel** in Telegram admin settings. Ordinary bot installation and updates do not install the dashboard. Its title follows the bot's message display name.

## 🛠 Manage & update

Open the management menu from any directory:

```bash
sudo sui-bot
```

Useful direct commands:

```bash
sudo sui-bot restart
sui-bot logs --follow
sudo sui-bot update
sudo sui-bot uninstall
```

Updates preserve the managed configuration and bot data; **you do not need to move backups again** on an existing SUI Bot installation. Make a backup before updating. Uninstallation offers destructive removal options — save anything you want to keep first.

## 💾 Backups & important data

In Telegram, use **Settings → Administration → Backup & Restore** to receive a bot backup. To restore it, send `/restore` and upload that file as the administrator.

Bot backups include assignments, settings, languages, guides, metrics, and sales plans/orders. **They do not replace the separate S-UI database backup**, and exclude the live bot and panel API tokens. Keep them private: they still contain customer and payment information. Restore matching bot/panel backups carefully; an older order ledger may not reflect accounts created afterwards.

Guide media and receipts use Telegram file references; restore them with the same Telegram bot.

- **Bot data and downloaded database backups:** `/var/lib/sui-bot` (database files are in its `backups` folder).
- **Credentials:** `/etc/sui-bot/sui-bot.env`.

For migration from an older installation, stop the bot before copying its state, preserve the filenames, and give the `sui-bot` service user ownership. Copying only a panel database does not restore Telegram assignments.

