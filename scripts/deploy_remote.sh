#!/usr/bin/env bash
set -euo pipefail

mkdir -p "$APP_DIR"
cd "$APP_DIR"

if [ -d .git ]; then
  git fetch origin main
  git checkout main
  git reset --hard origin/main
else
  git clone --branch main https://github.com/7b964ktxpc-web/pricewatcher-telegram.git .
fi

DEPLOYED_SHA="$(git rev-parse HEAD)"
test "$DEPLOYED_SHA" = "$EXPECTED_SHA"
echo "DEPLOYED SHA: $DEPLOYED_SHA"

: > .env.telegram
write_secret() {
  key="$1"
  value="$2"
  if [ -n "$value" ]; then
    printf '%s=' "$key" >> .env.telegram
    printf '%s' "$value" | base64 -d >> .env.telegram
    printf '%s\n' '' >> .env.telegram
  fi
}

write_secret TELEGRAM_BOT_TOKEN "$TOKEN_B64"
write_secret ADMIN_BOT_TOKEN "$ADMIN_TOKEN_B64"
write_secret ADMIN_USER_IDS "$ADMIN_IDS_B64"
write_secret DEEPSEEK_API_KEY "$DEEPSEEK_B64"
write_secret HF_TOKEN "$HF_B64"
write_secret GROQ_API_KEY "$GROQ_B64"
write_secret GEMINI_API_KEY "$GEMINI_B64"
write_secret WB_API_TOKEN "$WB_API_B64"
write_secret YANDEX_MARKET_API_KEY "$YM_API_B64"
write_secret YANDEX_MARKET_BUSINESS_ID "$YM_BUSINESS_B64"
write_secret WB_FEED_URL "$WB_FEED_B64"
write_secret OZON_FEED_URL "$OZON_FEED_B64"
write_secret YANDEX_MARKET_FEED_URL "$YM_FEED_B64"
write_secret SIMALAND_FEED_URL "$SIMALAND_FEED_B64"
write_secret DETMIR_FEED_URL "$DETMIR_FEED_B64"
write_secret AKUSHERSTVO_FEED_URL "$AKUSHERSTVO_FEED_B64"
write_secret KORABLIK_FEED_URL "$KORABLIK_FEED_B64"

chmod 600 .env.telegram
COMPOSE=(docker compose --env-file .env.telegram)
"${COMPOSE[@]}" config >/dev/null
"${COMPOSE[@]}" up -d --build --remove-orphans
"${COMPOSE[@]}" ps

for i in $(seq 1 15); do
  if curl -fsS --max-time 5 http://127.0.0.1:8010/health >/dev/null; then
    echo "HEALTH OK"
    "${COMPOSE[@]}" ps --status running --services | grep -qx marketplace-parser
    "${COMPOSE[@]}" ps --status running --services | grep -qx telegram-bot
    "${COMPOSE[@]}" ps --status running --services | grep -qx admin-bot
    "${COMPOSE[@]}" ps --status running --services | grep -qx watchlist-checker
    echo "ALL SERVICES RUNNING"
    curl -fsS --max-time 10 http://127.0.0.1:8010/api/readiness
    echo
    exit 0
  fi
  echo "Waiting for application... $i/15"
  sleep 2
done

echo "DEPLOY VERIFICATION FAILED"
"${COMPOSE[@]}" ps
"${COMPOSE[@]}" logs --tail=200
exit 1
