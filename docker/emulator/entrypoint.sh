#!/bin/sh
set -e
envsubst < /templates/config.template.json > /app/Config/config.json
exec dotnet "/app/Plus Emulator.dll"
