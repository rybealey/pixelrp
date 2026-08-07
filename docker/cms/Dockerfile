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
RUN npm ci && npm run build:atom

FROM php:8.5-fpm-alpine
RUN apk add --no-cache icu-dev libzip-dev libpng-dev libjpeg-turbo-dev freetype-dev oniguruma-dev \
 && apk add --no-cache --virtual .build-deps linux-headers \
 && docker-php-ext-configure gd --with-jpeg --with-freetype \
 && docker-php-ext-install pdo_mysql bcmath intl zip gd exif sockets \
 && apk del .build-deps
WORKDIR /var/www/html
COPY --from=vendor /app .
COPY --from=assets /app/public/build ./public/build
COPY docker/cms/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh && chown -R www-data:www-data storage bootstrap/cache
ENTRYPOINT ["/entrypoint.sh"]
CMD ["php-fpm"]
