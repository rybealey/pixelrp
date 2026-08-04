# Arcturus Morningstar 4.0.x runtime. The jar is NOT baked in — it is a
# user-supplied artifact bind-mounted from ./artifacts/arcturus (see
# artifacts/README.md), so this image builds fine before artifacts exist and
# the entrypoint gives a precise error at runtime instead.
FROM eclipse-temurin:21-jre

COPY entrypoint.sh /usr/local/bin/pixelrp-emulator-entrypoint
RUN chmod +x /usr/local/bin/pixelrp-emulator-entrypoint

# /app is a bind mount of ./data/emulator — config.ini and logs persist there.
WORKDIR /app
ENTRYPOINT ["pixelrp-emulator-entrypoint"]
