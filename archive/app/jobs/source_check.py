"""
Source URL check job (future).

Scheduled job that periodically checks `source.url` for HTTP 200
and updates `source.quality` to 'rotted' on persistent failures,
flagging the URL for Wayback Machine archival.

Not in Phase 1-7 build prompt scope; placeholder for later.
"""
