FROM composer:2 AS vendor
WORKDIR /app
# ext-sockets is required at boot (habbo.php uses AF_INET) so post-autoload-dump
# scripts (artisan package:discover) can run during `composer install`.
RUN apk add --no-cache --virtual .build-deps linux-headers \
 && docker-php-ext-install sockets \
 && apk del .build-deps
COPY cms/ .
RUN composer install --no-dev --no-interaction --ignore-platform-req=ext-* --optimize-autoloader

FROM node:22-alpine AS assets
WORKDIR /app
COPY cms/ .
# The Filament housekeeping theme's CSS does
# `@import "../../../../vendor/filament/filament/resources/css/theme.css"`, so
# the asset build needs Composer's output present — hence vendor stage first.
COPY --from=vendor /app/vendor ./vendor
RUN npm ci && npm run build:pixelrp

FROM php:8.5-fpm-alpine
RUN apk add --no-cache icu-dev libzip-dev libpng-dev libjpeg-turbo-dev freetype-dev oniguruma-dev \
 && apk add --no-cache --virtual .build-deps linux-headers \
 && docker-php-ext-configure gd --with-jpeg --with-freetype \
 && docker-php-ext-install pdo_mysql bcmath intl zip gd exif sockets \
 && apk del .build-deps
WORKDIR /var/www/html
COPY --from=vendor /app .
COPY --from=assets /app/public/build ./public/build
# Pristine copy of public/ at a path the cms-public volume does not shadow.
# That volume is only seeded from the image when Docker first creates it and is
# never refreshed afterwards, so without this the built theme assets and any
# new file under public/ can never reach an existing install. The deploy syncs
# this over the volume; it overlays rather than replaces, leaving runtime
# content (storage symlink, generated logos) alone.
RUN cp -a /var/www/html/public /opt/cms-public
COPY docker/cms/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh && chown -R www-data:www-data storage bootstrap/cache
# Housekeeping upload roots (ads_path_filesystem / badge_path_filesystem).
# Created here so the named volume mounted at /var/www/gamedata inherits
# www-data ownership on first create — php-fpm runs as www-data and cannot
# create these under the root-owned /var/www itself.
RUN mkdir -p /var/www/gamedata/custom /var/www/gamedata/c_images/album1584 \
 && chown -R www-data:www-data /var/www/gamedata
ENTRYPOINT ["/entrypoint.sh"]
CMD ["php-fpm"]
