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
    failed=0
    for service in marketplace-parser telegram-bot admin-bot watchlist-checker; do
      if ! "${COMPOSE[@]}" ps --status running --services | grep -qx "$service"; then
        echo "SERVICE NOT RUNNING: $service"
        failed=1
      fi
    done
    if [ "$failed" -eq 0 ]; then
      echo "ALL SERVICES RUNNING"
      readiness="$(curl -fsS --max-time 10 http://127.0.0.1:8010/api/readiness)"
      printf '%s\n' "$readiness"

      echo "RUNNING SEARCH SMOKE TEST"
      search_response="$(curl -fsS --max-time 45 --get \
        --data-urlencode 'q=футболка мальчик 5 лет до 1000 рублей' \
        --data-urlencode 'limit=3' \
        http://127.0.0.1:8010/api/agent/search)"
      printf '%s\n' "$search_response"
      if ! printf '%s' "$search_response" | grep -Eq '"ready"[[:space:]]*:[[:space:]]*true'; then
        echo "SEARCH SMOKE TEST FAILED: /api/agent/search did not return ready=true"
        exit 1
      fi
      echo "SEARCH SMOKE TEST OK"
      exit 0
    fi
    echo "Service verification failed; collecting recent logs"
    for service in telegram-bot admin-bot watchlist-checker; do
      echo "===== $service logs ====="
      "${COMPOSE[@]}" logs --no-color --tail=80 "$service" || true
    done
    exit 1
  fi
  echo "Waiting for application... $i/15"
  sleep 2
done

echo "DEPLOY VERIFICATION FAILED"
"${COMPOSE[@]}" ps
"${COMPOSE[@]}" logs --no-color --tail=200
exit 1
