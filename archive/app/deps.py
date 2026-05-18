"""
FastAPI dependencies.

Phase 1: stub. The real auth/role dependencies are added in Phase 3
(`get_current_user`, `require_team_role`, `require_editor`, etc.)
once the fake-login system exists. Until then, route handlers don't
require auth at all — they just read from the public DB.

Adding the placeholder file now keeps imports stable so route modules
can do `from app.deps import get_db` without breaking when we add
auth deps to the same file.
"""

from .db import get_db  # re-export for convenience

__all__ = ["get_db"]
