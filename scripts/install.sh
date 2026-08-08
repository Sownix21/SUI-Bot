#!/usr/bin/env bash
set -Eeuo pipefail

if [[ ${EUID} -ne 0 ]]; then
  echo "Run this installer as root: sudo ./scripts/install.sh" >&2
  exit 1
fi

for command in python3 systemctl useradd install cp chown chmod; do
  command -v "${command}" >/dev/null || { echo "Missing required command: ${command}" >&2; exit 1; }
done

SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INSTALL_DIR=/opt/obscura-bot
CONFIG_DIR=/etc/obscura-bot
ENV_FILE=${CONFIG_DIR}/obscura-bot.env
SERVICE_FILE=/etc/systemd/system/obscura-bot.service

if ! id obscura-bot >/dev/null 2>&1; then
  useradd --system --home-dir /var/lib/obscura-bot --shell /usr/sbin/nologin obscura-bot
fi

install -d -m 0755 "${INSTALL_DIR}"
install -d -m 0750 -o root -g obscura-bot "${CONFIG_DIR}"
if [[ ${SOURCE_DIR} != ${INSTALL_DIR} ]]; then
  cp -a "${SOURCE_DIR}/." "${INSTALL_DIR}/"
fi
rm -rf "${INSTALL_DIR}/.venv"

python3 -m venv "${INSTALL_DIR}/.venv"
"${INSTALL_DIR}/.venv/bin/python" -m pip install --upgrade pip
"${INSTALL_DIR}/.venv/bin/pip" install "${INSTALL_DIR}"
chown -R root:obscura-bot "${INSTALL_DIR}"
chmod -R g+rX "${INSTALL_DIR}"
install -d -m 0755 /usr/local/bin
install -m 0755 "${SOURCE_DIR}/deploy/sui-bot" /usr/local/bin/sui-bot

write_env_value() {
  local key=$1 value=$2
  [[ ${value} != *$'\n'* && ${value} != *$'\r'* ]] || { echo "${key} cannot contain newlines" >&2; exit 1; }
  value=${value//\\/\\\\}
  value=${value//\"/\\\"}
  printf '%s="%s"\n' "${key}" "${value}" >>"${ENV_FILE}"
}

if [[ ! -f ${ENV_FILE} ]]; then
  install -m 0600 -o root -g obscura-bot /dev/null "${ENV_FILE}"
  if [[ -t 0 ]]; then
    read -r -p "S-UI URL (HTTPS): " sui_host
    read -r -s -p "S-UI token: " sui_token; echo
    read -r -s -p "Telegram bot token: " bot_token; echo
    read -r -p "Admin Telegram ID: " admin_id
    read -r -p "Fallback subscription URL: " fallback_uri
    write_env_value SUI_HOST "${sui_host}"
    write_env_value SUI_TOKEN "${sui_token}"
    write_env_value BOT_TOKEN "${bot_token}"
    write_env_value ADMIN_TELEGRAM_ID "${admin_id}"
    write_env_value FALLBACK_SUB_URI "${fallback_uri}"
    write_env_value ALLOW_INSECURE_HTTP "false"
  else
    install -m 0600 -o root -g obscura-bot "${SOURCE_DIR}/.env.example" "${ENV_FILE}"
    echo "Created ${ENV_FILE}; replace placeholder values, then run this installer again." >&2
    exit 2
  fi
fi

install -m 0644 "${SOURCE_DIR}/deploy/systemd/obscura-bot.service" "${SERVICE_FILE}"
systemctl daemon-reload
systemctl enable obscura-bot.service
systemctl restart obscura-bot.service

echo "SUI Bot installed and started."
echo "Status: systemctl status obscura-bot"
echo "Logs:   journalctl -u obscura-bot -f"
