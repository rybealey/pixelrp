# nitro-react, built from source at a pinned commit (see NITRO_REF in .env).

# ── Stage 1: build (README: Node >= 18; yarn.lock is Yarn Classic v1) ──
FROM node:20-alpine AS build
RUN apk add --no-cache git
ARG NITRO_REF=75ff874b73d5fc5672a38c536444efa0f0d27e8f
RUN git clone https://github.com/billsonnn/nitro-react.git /src \
    && cd /src && git checkout "$NITRO_REF"
WORKDIR /src
RUN yarn install --frozen-lockfile
# Headroom for vite in memory-capped Docker builds (a cap, not a reservation —
# harmless if unnecessary; community reports occasional OOMs without it).
ENV NODE_OPTIONS=--max-old-space-size=4096
# Plain `yarn build`, NOT build:prod — build:prod merely prepends a
# network-dependent (and upstream-deprecated) browserslist DB update.
RUN yarn build

# ── Stage 2: serve ──
FROM nginx:alpine
# jq powers the runtime config render (render-config.sh).
RUN apk add --no-cache jq
COPY --from=build /src/dist /usr/share/nginx/html
# Keep the pinned ref's config examples as render bases: render-config.sh
# rewrites ONLY our keys into them at container start, so upstream config
# evolution never requires re-vendoring a 31 KB JSON here.
RUN mv /usr/share/nginx/html/renderer-config.json.example /usr/share/nginx/html/renderer-config.base.json \
    && mv /usr/share/nginx/html/ui-config.json.example /usr/share/nginx/html/ui-config.base.json
COPY default.conf /etc/nginx/conf.d/default.conf
# nginx's stock entrypoint runs every /docker-entrypoint.d/*.sh before nginx.
COPY render-config.sh /docker-entrypoint.d/90-pixelrp-render-config.sh
RUN chmod +x /docker-entrypoint.d/90-pixelrp-render-config.sh
