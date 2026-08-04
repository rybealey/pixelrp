# One-shot asset converter (billsonnn/nitro-converter, pinned).
# Runs via `make convert-assets` — never part of the normal `make up` stack.
# Converts the user's SWF pack (./artifacts/flash-assets, mounted ro) plus
# official furniture into .nitro bundles + gamedata JSONs, written directly
# into ./artifacts/nitro-assets (the volume the nitro service serves).
FROM node:20-alpine
RUN apk add --no-cache git bash
ARG CONVERTER_REF=e0a1800a83feda5f9b1b5cfde7fed0181de7b06f
RUN git clone https://github.com/billsonnn/nitro-converter.git /conv \
    && cd /conv && git checkout "$CONVERTER_REF"
WORKDIR /conv
RUN yarn install --silent && yarn build

COPY entrypoint.sh /usr/local/bin/pixelrp-converter-entrypoint
RUN chmod +x /usr/local/bin/pixelrp-converter-entrypoint
ENTRYPOINT ["pixelrp-converter-entrypoint"]
