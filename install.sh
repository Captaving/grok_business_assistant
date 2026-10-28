#!/usr/bin/env bash
# Установка (и обновление) бота-сводочника голосовых на Ubuntu/Debian.
# Запуск из папки с ботом:  sudo bash install.sh
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$APP_DIR/.env"
SERVICE="voice-summary-bot"
APP_USER="voicebot"

say()  { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
ok()   { printf '\033[1;32m[✓] %s\033[0m\n' "$*"; }
warn() { printf '\033[1;33m[!] %s\033[0m\n' "$*"; }
die()  { printf '\033[1;31m[x] %s\033[0m\n' "$*" >&2; exit 1; }

# ask VAR "вопрос" [значение по умолчанию]; читаем из терминала, даже если stdin занят
ask() {
  local value
  read -r -p "$2${3:+ [$3]}: " value < /dev/tty
  value="${value:-${3:-}}"
  value="${value//[[:space:]]/}"
  printf -v "$1" '%s' "$value"
}

[ "$(id -u)" -eq 0 ] || die "Запусти через sudo: sudo bash $0"
[ -f "$APP_DIR/bot.py" ] || die "Не нашёл bot.py рядом с install.sh"

say "Ставлю системные пакеты"
if command -v apt-get >/dev/null; then
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -qq
  apt-get install -y -qq python3 python3-venv python3-pip curl ca-certificates >/dev/null
else
  warn "Это не Debian/Ubuntu — пропускаю apt. Нужны python3 (3.10+), python3-venv и curl."
fi
python3 -c 'import sys; sys.exit(sys.version_info < (3, 10))' \
  || die "Нужен Python 3.10+, а стоит $(python3 -V 2>&1). Обнови систему (Ubuntu 22.04+ / Debian 12+)."
ok "$(python3 -V)"

say "Создаю системного пользователя $APP_USER"
id -u "$APP_USER" >/dev/null 2>&1 || useradd --system --no-create-home --shell /usr/sbin/nologin "$APP_USER"
su -s /bin/sh "$APP_USER" -c "test -r '$APP_DIR/bot.py'" \
  || die "Пользователь $APP_USER не может читать $APP_DIR. Склонируй бота в /opt/voice-summary-bot (см. README)."
ok "Пользователь $APP_USER"

say "Ставлю Python-зависимости (минуту-другую)"
python3 -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/pip" install -q --upgrade pip
"$APP_DIR/.venv/bin/pip" install -q -r "$APP_DIR/requirements.txt"
ok "Зависимости установлены"

configure=1
if [ -f "$ENV_FILE" ]; then
  ask answer "Настройки (.env) уже есть. Ввести токены заново? (y/N)" "n"
  [[ "$answer" =~ ^[YyДд] ]] || configure=0
fi

if [ "$configure" -eq 1 ]; then
  say "Настройка"

  while true; do
    ask BOT_TOKEN "Токен бота от @BotFather"
    resp="$(curl -s --max-time 15 "https://api.telegram.org/bot${BOT_TOKEN}/getMe" || true)"
    if [[ "$resp" == *'"ok":true'* ]]; then
      BOT_USERNAME="$(sed -n 's/.*"username":"\([^"]*\)".*/\1/p' <<<"$resp")"
      ok "Токен рабочий: @$BOT_USERNAME"
      break
    fi
    warn "Telegram не принял токен. Скопируй его из @BotFather целиком (вида 123456:ABC...)."
  done

  while true; do
    ask OWNER_ID "Твой Telegram ID (число; узнать можно у @userinfobot)"
    [[ "$OWNER_ID" =~ ^[0-9]+$ ]] && break
    warn "ID — это только цифры, например 123456789"
  done

  while true; do
    ask GROQ_API_KEY "Ключ Groq (бесплатно: console.groq.com → API Keys)"
    code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 15 \
      -H "Authorization: Bearer ${GROQ_API_KEY}" https://api.groq.com/openai/v1/models || true)"
    if [ "$code" = "200" ]; then ok "Ключ Groq рабочий"; break; fi
    if [ "$code" = "401" ]; then warn "Groq не принял ключ, попробуй ещё раз"; continue; fi
    warn "Не смог проверить ключ (ответ: ${code:-нет связи}). Сохраняю как есть — проверь потом логи."
    break
  done

  while true; do
    ask BATCH_DELAY "Через сколько секунд тишины делать сводку" "180"
    [[ "$BATCH_DELAY" =~ ^[0-9]+$ ]] && break
    warn "Нужно число секунд"
  done

  ask TIMEZONE "Часовой пояс" "Europe/Moscow"

  umask 077
  cat > "$ENV_FILE" <<EOF
BOT_TOKEN=$BOT_TOKEN
OWNER_ID=$OWNER_ID
GROQ_API_KEY=$GROQ_API_KEY
BATCH_DELAY=$BATCH_DELAY
TIMEZONE=$TIMEZONE
EOF
  umask 022
  ok "Настройки сохранены в $ENV_FILE"
fi
chown "root:$APP_USER" "$ENV_FILE"
chmod 640 "$ENV_FILE"

say "Запускаю службу $SERVICE"
cat > "/etc/systemd/system/$SERVICE.service" <<EOF
[Unit]
Description=Telegram voice summary bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$APP_USER
WorkingDirectory=$APP_DIR
ExecStart=$APP_DIR/.venv/bin/python bot.py
Environment=PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
Restart=always
RestartSec=5
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=read-only
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable "$SERVICE" >/dev/null 2>&1
systemctl restart "$SERVICE"
sleep 5

if systemctl is-active --quiet "$SERVICE"; then
  ok "Бот работает"
  cat <<EOF

Что дальше:
  1. Напиши своему боту в Telegram /start — он ответит, что всё ок.
  2. @BotFather → /mybots → твой бот → Bot Settings → Business Mode → Turn on.
  3. Telegram: Настройки → Изменить профиль → Автоматизация чатов → выбери бота →
     «Только выбранные чаты» → чат с начальником. Право «отвечать» можно выключить.

Логи:        journalctl -u $SERVICE -f
Перезапуск:  systemctl restart $SERVICE
EOF
else
  warn "Служба не запустилась. Последние строки лога:"
  journalctl -u "$SERVICE" -n 30 --no-pager || true
  exit 1
fi
