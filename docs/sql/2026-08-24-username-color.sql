-- Username color (Settings > Social > Username > Color). Empty = default (black).
ALTER TABLE `user_ui_settings`
  ADD COLUMN `username_color` VARCHAR(7) NOT NULL DEFAULT '' AFTER `header_color`;
