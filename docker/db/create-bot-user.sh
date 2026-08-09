#!/bin/sh
# Creates the bot service's low-privilege MySQL user on first database init.
# The bot's queries are `UPDATE users SET auth_ticket = ? WHERE username = ?`
# (bot/src/sso.ts) and `SELECT value FROM server_settings WHERE key =
# 'bot.enabled'` (bot/src/flag.ts, the in-game :bot toggle), so it gets
# exactly the column privileges those statements need and nothing else — full
# app credentials in the bot container would put the whole database in reach
# of a bot compromise.
#
# Runs from /docker-entrypoint-initdb.d, i.e. only when the data volume is
# first created. For an existing volume, apply the CREATE USER/GRANT by hand —
# see bot/README.md "Database Access".
#
# Must stay executable (git tracks the bit): mysql's entrypoint *sources*
# non-executable .sh init files, which would leak this script's shell state
# into the entrypoint itself.
set -eu

if [ -n "${BOT_DB_USER:-}" ] && [ -n "${BOT_DB_PASSWORD:-}" ]; then
  mysql -uroot -p"$MYSQL_ROOT_PASSWORD" <<SQL
CREATE USER IF NOT EXISTS '$BOT_DB_USER'@'%' IDENTIFIED BY '$BOT_DB_PASSWORD';
GRANT SELECT (username), UPDATE (auth_ticket) ON \`$MYSQL_DATABASE\`.\`users\` TO '$BOT_DB_USER'@'%';
GRANT SELECT (\`key\`, \`value\`) ON \`$MYSQL_DATABASE\`.\`server_settings\` TO '$BOT_DB_USER'@'%';
SQL
  echo "[init] created bot MySQL user '$BOT_DB_USER' (SELECT(username), UPDATE(auth_ticket) on users; SELECT(key,value) on server_settings)"
else
  echo "[init] BOT_DB_USER/BOT_DB_PASSWORD not set — skipping bot MySQL user (bot falls back to the app user)"
fi
