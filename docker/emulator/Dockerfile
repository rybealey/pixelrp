FROM mcr.microsoft.com/dotnet/sdk:7.0 AS build
WORKDIR /src
COPY emulator/ .
RUN dotnet publish "Plus Emulator.csproj" -c Release -o /app

FROM mcr.microsoft.com/dotnet/runtime:7.0
RUN apt-get update && apt-get install -y --no-install-recommends gettext-base && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY --from=build /app .
COPY docker/emulator/config.template.json /templates/config.template.json
COPY docker/emulator/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
