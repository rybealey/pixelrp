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

# A fresh .env means fresh DB passwords — but MariaDB only applies credentials
# on an EMPTY datadir. Generating new secrets against existing data guarantees
# auth failures, so refuse instead of desyncing.
if [ -d data/db ] && [ -n "$(find data/db -mindepth 1 -maxdepth 1 2>/dev/null | head -1)" ]; then
  echo >&2 "ERROR: .env is missing but ./data/db already contains a database that was"
  echo >&2 "ERROR: initialized with the OLD secrets. New secrets would not match it."
  echo >&2 "ERROR: Either restore your previous .env, or wipe the data with 'make reset'."
  exit 1
fi

command -v openssl >/dev/null || { echo >&2 "ERROR: openssl not found — cannot generate secrets."; exit 1; }

# Standalone assignments so an openssl failure aborts (set -e ignores failing
# command substitutions used inside another command's arguments).
app_key="$(openssl rand -base64 32)"

while IFS= read -r line; do
  case "$line" in
    APP_KEY=__GENERATE_APP_KEY__)
      printf 'APP_KEY=base64:%s\n' "$app_key" ;;
    *=__GENERATE__)
      secret="$(openssl rand -hex 16)"
      printf '%s=%s\n' "${line%%=*}" "$secret" ;;
    *)
      printf '%s\n' "$line" ;;
  esac
done < .env.example > .env.tmp
mv .env.tmp .env

echo "Generated .env with fresh secrets."
