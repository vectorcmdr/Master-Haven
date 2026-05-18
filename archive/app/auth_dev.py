"""
Dev-only fake login.

Phase 1: stub. Phase 3 fleshes this out with:
- GET  /api/v1/auth/dev/users      list pickable seed users
- POST /api/v1/auth/dev/login      set a signed session cookie
- POST /api/v1/auth/logout         clear it
- GET  /api/v1/auth/me             return current session user

All endpoints in this module 404 in production (gated by config.is_dev).
"""
