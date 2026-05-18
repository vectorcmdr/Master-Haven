"""
Discord role sync job (Phase 7).

Pulls member rolls from the VH server (at :00/:30) and the Archivist
server (at :15/:45), staggered to avoid hitting Discord's API rate
limit. For each guild member with a mapped role: create/update
archive_user, set base_role. For each archive_user not present in
either server: demote base_role to 'reader'.

is_editor and is_admin are NOT synced — those are archive-native,
set via the admin UI.

Phase 1: stub.
"""
