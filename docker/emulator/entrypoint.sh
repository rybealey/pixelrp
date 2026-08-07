#!/bin/sh
set -e
envsubst < /templates/config.template.json > /app/Config/config.json

# The db service's healthcheck only proves the MySQL root account can ping;
# the app connects as DB_USER/DB_PASSWORD, and on a cold start (fresh
# container, first boot) that account's grants can lag a few seconds behind
# "healthy". PlusEnvironment.Start() has no retry for a failed initial
# connection - it just blocks forever on Console.ReadKey() - so we must not
# exec dotnet until a real login with the app's own credentials succeeds.
echo "Waiting for MySQL (${DB_HOST}) to accept connections as ${DB_USER}..."
attempt=0
until mysql -h "$DB_HOST" -u "$DB_USER" -p"$DB_PASSWORD" "$DB_NAME" -e "SELECT 1" >/dev/null 2>&1; do
  attempt=$((attempt + 1))
  if [ "$attempt" -ge 60 ]; then
    echo "Gave up waiting for MySQL after ${attempt} attempts." >&2
    exit 1
  fi
  sleep 1
done
echo "MySQL is ready."

exec dotnet "/app/Plus Emulator.dll"
