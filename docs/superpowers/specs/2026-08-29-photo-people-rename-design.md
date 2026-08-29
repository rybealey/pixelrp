# Photo People vs Username Renames — Design

**Date:** 2026-08-29 · **Scope:** emulator read path · **Branch:** beta

## Problem

Photos' People groups key on tag usernames captured at photo time
(`camera_web_users.username` snapshots). When a player renames (Ryan →
Yavn on beta), their old photos stay grouped under the dead name.

## Design (approved)

Resolve at read time. `camera_web_users` already stores the tagged
player's validated `user_id`; the one query feeding the photo list
(RpPhotoLibrary) now LEFT JOINs `users` and serves
`COALESCE(u.username, t.username)` - the current name, with the
snapshot only as a fallback for deleted accounts. Renames reflect
instantly with no hook into any rename flow, and existing variances
self-heal with zero data fixes. This also matches the album queries,
which already JOIN `users` for live names; the tag query was the one
outlier.

Verified read-only against the live beta DB: the three photos tagged
`Ryan` resolve to `Yavn`; no orphaned tags exist.

## Files

- `emulator/Communication/Packets/Incoming/Camera/RpPhotoLibrary.cs`
- `CHANGELOG.md`
