"""
Discord OAuth.

Phase 1: stub. Phase 7 fleshes this out with:
- GET /api/v1/auth/discord/login     302 redirect to Discord
- GET /api/v1/auth/discord/callback  exchange code, create/update user

Uses the same session cookie machinery as auth_dev.py so the rest of
the app doesn't care which login path was taken.
"""
