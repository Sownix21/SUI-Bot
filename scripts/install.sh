#!/usr/bin/env bash
set -Eeuo pipefail

if [[ ${EUID} -ne 0 ]]; then
  echo "Run this installer as root: sudo ./scripts/install.sh" >&2
  exit 1
fi

SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ ! -f ${SOURCE_DIR}/pyproject.toml ]]; then
  for command in curl tar mktemp; do
    command -v "${command}" >/dev/null || { echo "Missing required command: ${command}" >&2; exit 1; }
  done
  bootstrap_dir=$(mktemp -d)
  trap 'rm -rf "${bootstrap_dir}"' EXIT
  curl --proto '=https' --tlsv1.2 -fsSL \
    https://github.com/Sownix21/SUI-Bot/archive/refs/heads/main.tar.gz \
    | tar -xz -C "${bootstrap_dir}" --strip-components=1
  bash "${bootstrap_dir}/scripts/install.sh"
  exit $?
fi

for command in python3 systemctl useradd install cp chown chmod; do
  command -v "${command}" >/dev/null || { echo "Missing required command: ${command}" >&2; exit 1; }
done

INSTALL_DIR=/opt/sui-bot
CONFIG_DIR=/etc/sui-bot
STATE_DIR=/var/lib/sui-bot
ENV_FILE=${CONFIG_DIR}/sui-bot.env
SERVICE_FILE=/etc/systemd/system/sui-bot.service

if ! id sui-bot >/dev/null 2>&1; then
  useradd --system --home-dir /var/lib/sui-bot --shell /usr/sbin/nologin sui-bot
fi

install -d -m 0755 "${INSTALL_DIR}"
install -d -m 0750 -o root -g sui-bot "${CONFIG_DIR}"
install -d -m 0750 -o sui-bot -g sui-bot "${STATE_DIR}"
if [[ ${SOURCE_DIR} != ${INSTALL_DIR} ]]; then
  # Copy only release files. Local .env files, Git metadata, caches, and test
  # artifacts must never become part of the system installation.
  rm -rf "${INSTALL_DIR}/src" "${INSTALL_DIR}/deploy" "${INSTALL_DIR}/scripts"
  cp -a "${SOURCE_DIR}/src" "${SOURCE_DIR}/deploy" "${SOURCE_DIR}/scripts" "${INSTALL_DIR}/"
  for release_file in pyproject.toml README.md README.fa.md LICENSE .env.example; do
    if [[ -f ${SOURCE_DIR}/${release_file} ]]; then
      cp -a "${SOURCE_DIR}/${release_file}" "${INSTALL_DIR}/${release_file}"
    fi
  done
fi
rm -rf "${INSTALL_DIR}/.venv"

if ! python3 -m venv "${INSTALL_DIR}/.venv"; then
  rm -rf "${INSTALL_DIR}/.venv"
  echo "Python venv support is missing; attempting to install it..." >&2
  if command -v apt-get >/dev/null; then
    apt-get update
    apt-get install -y python3-venv git
  elif command -v dnf >/dev/null; then
    dnf install -y python3 python3-pip git
  elif command -v yum >/dev/null; then
    yum install -y python3 python3-pip git
  else
    echo "Install Python venv support for your distribution and run the installer again." >&2
    exit 1
  fi
  python3 -m venv "${INSTALL_DIR}/.venv"
fi
if ! command -v git >/dev/null; then
  echo "Git is required by the built-in updater; attempting to install it..." >&2
  if command -v apt-get >/dev/null; then
    apt-get update
    apt-get install -y git
  elif command -v dnf >/dev/null; then
    dnf install -y git
  elif command -v yum >/dev/null; then
    yum install -y git
  else
    echo "Install git to use 'sui-bot update'." >&2
  fi
fi
"${INSTALL_DIR}/.venv/bin/python" -m pip install --upgrade pip
"${INSTALL_DIR}/.venv/bin/pip" install "${INSTALL_DIR}"
chown -R root:sui-bot "${INSTALL_DIR}"
chmod -R g+rX "${INSTALL_DIR}"
chown -R sui-bot:sui-bot "${STATE_DIR}"
chmod -R u+rwX,g+rX,o-rwx "${STATE_DIR}"
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
  install -m 0600 -o root -g sui-bot /dev/null "${ENV_FILE}"
  if [[ -r /dev/tty ]]; then
    read -r -p "S-UI URL (HTTPS): " sui_host </dev/tty
    read -r -s -p "S-UI token: " sui_token </dev/tty; echo
    read -r -s -p "Telegram bot token: " bot_token </dev/tty; echo
    read -r -p "Admin Telegram ID: " admin_id </dev/tty
    write_env_value SUI_HOST "${sui_host}"
    write_env_value SUI_TOKEN "${sui_token}"
    write_env_value BOT_TOKEN "${bot_token}"
    write_env_value ADMIN_TELEGRAM_ID "${admin_id}"
    write_env_value ALLOW_INSECURE_HTTP "false"
    write_env_value REDIS_ENABLED "false"
  else
    install -m 0600 -o root -g sui-bot "${SOURCE_DIR}/.env.example" "${ENV_FILE}"
    echo "Created ${ENV_FILE}; replace placeholder values, then run this installer again." >&2
    exit 2
  fi
fi

chown root:sui-bot "${ENV_FILE}"
chmod 0600 "${ENV_FILE}"
SUI_BOT_SYSTEM_ENV_FILE="${ENV_FILE}" "${INSTALL_DIR}/.venv/bin/python" -m sui_bot.cli validate

install -m 0644 "${SOURCE_DIR}/deploy/systemd/sui-bot.service" "${SERVICE_FILE}"
systemctl daemon-reload
systemctl enable sui-bot.service
systemctl restart sui-bot.service
sleep 2

if ! systemctl is-active --quiet sui-bot.service; then
  echo "SUI Bot failed to remain active. Recent service logs:" >&2
  journalctl -u sui-bot.service -n 30 --no-pager >&2 || true
  exit 1
fi

echo "SUI Bot installed and started."
echo "Status: systemctl status sui-bot"
echo "Logs:   journalctl -u sui-bot -f"
