# AtomCMS (Laravel 11, PHP ^8.2). Source is cloned to ./cms/src on the HOST by
# `make up` so you can read and edit it; this build COPYs from there.

# ── Stage 1: front-end assets (Vite 6 needs Node 20+) ──
# npm install (not yarn/npm ci) mirrors AtomCMS's own CI: the repo commits a
# yarn.lock that is STALE vs package.json (--frozen-lockfile fails on it,
# verified 2026-08) and no package-lock.json exists.
FROM node:22-alpine AS assets
WORKDIR /build
COPY src/package.json ./
RUN npm install
COPY src/ ./
# Two vite builds are needed: build:atom (the site theme, what upstream CI
# runs) AND the base build (resources/css/app.css — the /installation wizard's
# layout requires it; a theme-only build 500s there with a ViteException,
# verified 2026-08). Both write public/build/manifest.json, each clobbering
# the other — so build both and merge the manifests.
RUN npm run build:atom \
    && cp -r public/build /tmp/build-atom \
    && npm run build \
    && cp -r /tmp/build-atom/assets/. public/build/assets/ \
    && node -e "const fs=require('fs');const a=JSON.parse(fs.readFileSync('/tmp/build-atom/manifest.json'));const b=JSON.parse(fs.readFileSync('public/build/manifest.json'));fs.writeFileSync('public/build/manifest.json',JSON.stringify({...a,...b}))"
# Replicate `yarn link:atom` (theme images into public/) with a real copy —
# a symlink would dangle across COPY --from.
RUN if [ -d resources/themes/atom/images ]; then \
      rm -rf public/images && cp -r resources/themes/atom/images public/images; \
    fi

# ── Stage 2: PHP runtime ──
FROM php:8.3-apache
# Extensions AtomCMS needs beyond the image defaults (research-verified):
#   sockets  — the AtomCMS RCON package (ext-sockets in composer.json)
#   pdo_mysql, gd — documented requirements; zip — composer dist installs;
#   opcache — cheap speedup. curl/fileinfo/mbstring/openssl ship enabled already.
RUN apt-get update && apt-get install -y --no-install-recommends \
      git unzip libpng-dev libjpeg62-turbo-dev libwebp-dev libfreetype6-dev libzip-dev \
    && docker-php-ext-configure gd --with-jpeg --with-freetype --with-webp \
    && docker-php-ext-install -j"$(nproc)" gd pdo_mysql sockets zip opcache \
    && a2enmod rewrite \
    && rm -rf /var/lib/apt/lists/*

COPY --from=composer:2 /usr/bin/composer /usr/bin/composer
COPY apache-vhost.conf /etc/apache2/sites-available/000-default.conf

WORKDIR /var/www/html
# Full source incl. the repo's committed auth.json (Bitbucket credentials for
# the laravel/nova housekeeping package — the most fragile dependency; see README).
COPY src/ ./

# AtomCMS declares six first-party packages as VCS repos with git@github.com:
# SSH URLs. Anonymous builds can't use them: the GitHub API driver dies on
# rate limits ("Could not authenticate against github.com"), and with the API
# driver disabled composer can't match SSH-form URLs to its git driver at all
# (it falls through to svn — both verified 2026-08). Fix, in the IMAGE COPY
# only: rewrite the URLs to https form and clone anonymously, no API involved.
# Optional GITHUB_TOKEN switches back to the (faster) API driver instead.
ARG GITHUB_TOKEN=""
RUN if [ -n "$GITHUB_TOKEN" ]; then \
      composer config -g github-oauth.github.com "$GITHUB_TOKEN"; \
    else \
      sed -i 's#git@github.com:#https://github.com/#g' composer.json \
      && composer config -g use-github-api false \
      && composer config -g github-protocols https; \
    fi \
    && composer install --no-dev --prefer-dist --no-interaction --no-progress --no-scripts \
    && composer clear-cache

# UPSTREAM BUG WORKAROUND (atom-retros/core dev-main, 2026-08): the package
# ships BackgroundSyncCommand.php whose class is misnamed `BadgeSyncCommand`
# (copy-paste duplicate), which fatals EVERY artisan call — the duplicate
# declaration breaks command auto-discovery, and the provider registers
# BackgroundSyncCommand::class so the class must exist under its file's name.
# Rename the class in place; no-op once upstream fixes the file.
RUN sed -i 's/^class BadgeSyncCommand /class BackgroundSyncCommand /' \
      vendor/atomcms/core/src/Console/Commands/BackgroundSyncCommand.php

# UPSTREAM BUG WORKAROUND (atomcms/theme dev-main, 2026-08): SitemapController
# chains ->map() directly onto the article query builder (no ->get()), so
# /sitemap 500s with "Call to undefined method Builder::map()" every time a
# crawler fetches it. Insert the missing ->get(); no-op once upstream fixes it.
RUN sed -i "s/->latest('id')$/->latest('id')->get()/" \
      vendor/atomcms/theme/src/Http/Controllers/SitemapController.php \
    && grep -q "latest('id')->get()" \
      vendor/atomcms/theme/src/Http/Controllers/SitemapController.php

# Built front-end (includes public/build and theme images) over the source copy.
COPY --from=assets /build/public ./public

COPY entrypoint.sh /usr/local/bin/pixelrp-cms-entrypoint
RUN chmod +x /usr/local/bin/pixelrp-cms-entrypoint

ENTRYPOINT ["pixelrp-cms-entrypoint"]
CMD ["apache2-foreground"]
