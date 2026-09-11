#!/usr/bin/with-contenv bashio
set -e

bashio::log.info "Görev Maliyet Hesaplayıcı (web sitesi) başlatılıyor..."

export TZ="$(bashio::config 'timezone')"
export WEB_PORT=8102
export INGRESS_PORT=8099

cd /app

exec python3 -u /app/web.py
