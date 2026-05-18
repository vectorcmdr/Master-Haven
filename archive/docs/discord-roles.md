# Discord role → Archive role mapping

> **Status: PLACEHOLDER.** Fill this in before Phase 7. Every row with
> `____________` in it must be replaced with a real value.

## How this file is used

The `app/jobs/discord_sync.py` job (Phase 7) reads this table at
container build time, parses it, and uses it to map Discord guild
membership + roles to `archive_user.base_role`.

- A user with ANY role from the **Historian** table on either guild
  becomes `base_role = 'historian'`.
- Otherwise, a user with any role from the **Diplomat** table on
  either guild becomes `base_role = 'diplomat'`.
- Otherwise (user is in a guild but not in either bucket) →
  `base_role = 'reader'`.
- A user not present in either guild is demoted to `reader` on next
  sync.

`is_editor` and `is_admin` are NOT controlled by Discord — they are
archive-native, granted via the admin UI. The sync job will never
flip those flags.

## Guild IDs

| Guild | Discord Guild ID |
|---|---|
| Voyager's Haven (VH) | `____________` |
| The Archivist        | `____________` |

(Get these via Discord's developer mode: right-click the guild icon →
Copy Server ID.)

## Role mapping

### Historian roles
Roles whose holders should receive `base_role = 'historian'`.

| Guild | Role name | Discord Role ID |
|---|---|---|
| Archivist | `____________` | `____________` |
| Archivist | `____________` | `____________` |
| VH        | `____________` | `____________` |

### Diplomat roles
Roles whose holders should receive `base_role = 'diplomat'`.

| Guild | Role name | Discord Role ID |
|---|---|---|
| VH        | `____________` | `____________` |
| VH        | `____________` | `____________` |
| Archivist | `____________` | `____________` |

### Reader / unmapped
Any guild member NOT in a historian or diplomat role above falls
through to `base_role = 'reader'`. No table needed.

## Notes

- Role IDs are stable across renames. Prefer matching by ID, not name.
  The "Role name" column is for human reference only.
- A user with roles in both buckets gets the higher one (historian
  > diplomat > reader).
- The sync job is staggered: VH at :00/:30, Archivist at :15/:45.
- A `discord_sync_log` row is written every run with users_added /
  users_updated / users_removed counts. Inspect via the admin endpoint.
