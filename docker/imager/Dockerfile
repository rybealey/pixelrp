# nitro-imager (billsonnn) — Node 18 required for node-canvas@2.x.
FROM node:18-bookworm AS build
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential libcairo2-dev libpango1.0-dev libjpeg-dev libgif-dev librsvg2-dev \
    && rm -rf /var/lib/apt/lists/*
COPY imager/package.json imager/package-lock.json ./
RUN npm ci
COPY imager/ ./
RUN npm run build

FROM node:18-bookworm AS runtime
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
      libcairo2 libpango-1.0-0 libpangocairo-1.0-0 libjpeg62-turbo libgif7 librsvg2-2 \
    && rm -rf /var/lib/apt/lists/*
COPY --from=build /app/node_modules ./node_modules
COPY --from=build /app/dist ./dist
COPY --from=build /app/config.json ./config.json
ENV AVATAR_SAVE_PATH=/cache
RUN mkdir -p /cache
CMD ["node", "dist/index.js"]
