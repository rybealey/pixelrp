#!/usr/bin/env bash
# Generates .env from .env.example, filling secrets. Never overwrites an
# existing .env (delete it yourself if you truly want fresh secrets — the DB
# keeps the old password in ./data/db, so regenerating breaks a live stack).
set -euo pipefail
cd "$(dirname "$0")/.."

if [ -f .env ]; then
  echo ".env already exists — leaving it untouched."
  exit 0
fi

while IFS= read -r line; do
  case "$line" in
    APP_KEY=__GENERATE_APP_KEY__)
      printf 'APP_KEY=base64:%s\n' "$(openssl rand -base64 32)" ;;
    *=__GENERATE__)
      printf '%s=%s\n' "${line%%=*}" "$(openssl rand -hex 16)" ;;
    *)
      printf '%s\n' "$line" ;;
  esac
done < .env.example > .env

echo "Generated .env with fresh secrets."
