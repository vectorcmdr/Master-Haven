# Centralization Roadmap Entry 9 — Side-effect Dispatch Helper

## Problem

Request handlers were doing side-effect work inline before returning. The
single-system approval handler was the canonical case: it ran ~10–15 SQL
queries inside one transaction, then opened a *second* connection mid-handler
to write an `add_activity_log()` row, then a *third* connection to invalidate
poster cache rows. End-to-end latency on a Pi 5 was ~30 seconds for a single
approval — most of it spent on the audit trail and cache work that the user
did not need to wait for.

The same pattern existed elsewhere (war-room webhook delivery did a
synchronous `requests.post(...)` to Discord with a 5-second timeout, blocking
the event loop), and it scaled badly: the 100-system batch upload returned a
504 Gateway Timeout from Nginx Proxy Manager because the inline loop
exceeded the 60-second proxy timeout.

The shared mistake: **request handlers were doing both the
must-be-transactional work and the can-fire-after-return work in one inline
sequence**. Anything that doesn't change what the response says — audit
logging, cache invalidation, webhook delivery, analytics writes — should
fire after the response is sent.

## Solution

`services/dispatch.py` exposes `fire_and_forget(callable_or_coro, *args, **kwargs)`.
It schedules an async callable on the running event loop via
`asyncio.create_task`, wraps the call in a try/except that logs failures at
WARNING and never propagates them, and keeps a strong reference so the task
isn't garbage-collected mid-flight.

For **synchronous** callables, route handlers inject FastAPI's built-in
`background_tasks: BackgroundTasks` dependency and call
`background_tasks.add_task(fn, *args, **kwargs)` directly. The two transports
look different on purpose — picking which one to use is a deliberate
decision, not something the helper hides.

No new dependencies. No Redis, no Celery, no message broker. The Pi runs a
single FastAPI process; we don't need a job-queue framework to schedule
post-response work.

## Where it lives

- Helper: [Haven-UI/backend/services/dispatch.py](../../Haven-UI/backend/services/dispatch.py)
- First callers:
  - [Haven-UI/backend/routes/approvals.py](../../Haven-UI/backend/routes/approvals.py) — single-system approval, batch approval (activity log + poster invalidation)
  - [Haven-UI/backend/routes/warroom.py](../../Haven-UI/backend/routes/warroom.py) — Discord webhook delivery
- Migration: none — this is pure Python, no schema change.
- Doc: [docs/centralization/dispatch.md](dispatch.md) — this file.

## Lesson

When you find yourself opening a fresh DB connection mid-handler, or doing a
`requests.post(...)` inline with a request-path transaction, that's a signal
the work belongs *after* the response, not inside it. The handler's job ends
once it has built the response and committed any state the response promises.
Anything else — telemetry, denormalized caches, push notifications — fires
asynchronously and is allowed to fail without taking the user's request with
it.

The audit log INSERT that participates in the approval transaction stays
inline. That's a transactional guarantee, not a side effect. The
post-commit `add_activity_log()` row, in contrast, is for a "recent activity"
feed nobody is waiting on — it can run a quarter-second later without any
user noticing.

The line is "does the response promise this happened?" If yes, inline. If
no, dispatch.
