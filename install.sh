\
#!/usr/bin/env bash
set -Eeuo pipefail

if [[ $EUID -ne 0 ]]; then
  echo "Запусти от root: sudo bash install.sh"
  exit 1
fi
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="/opt/tg-bot"
ENV_FILE="/etc/tg-bot.env"
SERVICE_FILE="/etc/systemd/system/tg-bot.service"

if [[ ! -f "$SCRIPT_DIR/bot.py" ]]; then
  echo "Не найден bot.py рядом с install.sh"
  exit 1
fi
if [[ ! -f "$SCRIPT_DIR/templates/login.html" || ! -f "$SCRIPT_DIR/templates/admin.html" ]]; then
  echo "Не найдены templates/login.html и templates/admin.html"
  exit 1
fi

read -r -s -p "Вставь Telegram BOT_TOKEN: " BOT_TOKEN; echo
if [[ -z "$BOT_TOKEN" ]]; then echo "BOT_TOKEN не может быть пустым"; exit 1; fi
read -r -p "Твой числовой Telegram ID (ADMIN_IDS): " ADMIN_IDS
if [[ ! "$ADMIN_IDS" =~ ^[0-9]+(,[0-9]+)*$ ]]; then
  echo "Нужен числовой Telegram ID; несколько ID можно через запятую."
  exit 1
fi
read -r -s -p "Придумай новый пароль админ-панели: " ADMIN_PASSWORD; echo
if [[ ${#ADMIN_PASSWORD} -lt 16 ]]; then
  echo "Используй пароль не короче 16 символов."
  exit 1
fi

apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y python3 python3-venv python3-pip

install -d -m 750 "$APP_DIR" "$APP_DIR/data" "$APP_DIR/templates"
install -m 640 "$SCRIPT_DIR/bot.py" "$APP_DIR/bot.py"
install -m 640 "$SCRIPT_DIR/requirements.txt" "$APP_DIR/requirements.txt"
install -m 640 "$SCRIPT_DIR/templates/login.html" "$APP_DIR/templates/login.html"
install -m 640 "$SCRIPT_DIR/templates/admin.html" "$APP_DIR/templates/admin.html"

python3 -m venv "$APP_DIR/venv"
"$APP_DIR/venv/bin/pip" install --upgrade pip
"$APP_DIR/venv/bin/pip" install -r "$APP_DIR/requirements.txt"

umask 077
cat > "$ENV_FILE" <<EOF
BOT_TOKEN=$BOT_TOKEN
ADMIN_PASSWORD=$ADMIN_PASSWORD
ADMIN_IDS=$ADMIN_IDS
WEB_PORT=8080
WEB_HOST=127.0.0.1
SUBSCRIPTION_STARS=1111
SUBSCRIPTION_DAYS=30
SUBSCRIPTION_GRAM=11
EOF
chmod 600 "$ENV_FILE"
unset BOT_TOKEN ADMIN_PASSWORD

cat > "$SERVICE_FILE" <<'EOF'
[Unit]
Description=Python Telegram Bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/opt/tg-bot
EnvironmentFile=/etc/tg-bot.env
ExecStart=/opt/tg-bot/venv/bin/python /opt/tg-bot/bot.py
Restart=always
RestartSec=5
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now tg-bot
echo
echo "Установка завершена. Статус службы:"
systemctl --no-pager --full status tg-bot || true
echo
echo "Последние логи:"
journalctl -u tg-bot -n 30 --no-pager || true
echo
echo "Веб-панель слушает только localhost:8080 для безопасности."
echo "На СВОЁМ компьютере запусти: ssh -L 8080:127.0.0.1:8080 root@IP_СЕРВЕРА"
echo "Затем открой http://127.0.0.1:8080 в браузере."
