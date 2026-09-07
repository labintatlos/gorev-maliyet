#!/usr/bin/with-contenv bashio
set -e

TOKEN="$(bashio::config 'telegram_bot_token')"
USERS="$(bashio::config 'authorized_user_ids')"
ADMINS="$(bashio::config 'admin_user_ids' || true)"
WEBAPP="$(bashio::config 'webapp_url' || true)"

if [[ -z "${TOKEN}" ]]; then
  bashio::log.fatal "Telegram bot token girilmemiş."
  exit 1
fi

if [[ -z "${USERS}" ]]; then
  bashio::log.fatal "Yetkili Telegram kullanıcı ID'si girilmemiş."
  exit 1
fi

export TELEGRAM_BOT_TOKEN="${TOKEN}"
export AUTHORIZED_USER_IDS="${USERS}"
export ADMIN_USER_IDS="${ADMINS}"
export WEBAPP_URL="${WEBAPP}"
export HISTORY_DB_PATH="/data/history.db"
export MARKET_DATA_PATH="/data/market_data.json"
export PYTHONUNBUFFERED=1

bashio::log.info "Görev Maliyet Telegram Botu başlatılıyor..."
exec python3 /app/bot.py
