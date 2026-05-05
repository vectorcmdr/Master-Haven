"""
Side-effect dispatch helper — Centralization Roadmap Entry 9.

The pattern: side effects (activity-log writes, poster invalidation, Discord
webhooks, etc.) fire AFTER the response is built — they must not block the
request, must not affect request success, and must never leak exceptions
back to the caller.

Two transports:
  1. Async callable → asyncio.create_task() (runs on the event loop after
     the handler returns)
  2. Sync callable → FastAPI's BackgroundTasks (caller injects the
     BackgroundTasks dependency and uses background_tasks.add_task() directly)

This module exposes only the async case via fire_and_forget(); for sync
callables, route handlers should accept `background_tasks: BackgroundTasks`
and call `background_tasks.add_task(fn, *args, **kwargs)` themselves. The
two paths intentionally look different so the caller has to pick one
deliberately rather than reaching for a magic helper.

No new dependencies. No Redis, no Celery, no message broker.

Errors policy: every dispatched callable is wrapped so that a raised
exception is logged at WARNING level and swallowed. Side effects MUST NOT
affect request success — that's the entire point of dispatch.
"""

import asyncio
import inspect
import logging
from typing import Any, Awaitable, Callable, Coroutine, Optional, Union

logger = logging.getLogger('control.room')

AsyncCallable = Union[Callable[..., Awaitable[Any]], Coroutine[Any, Any, Any]]


def fire_and_forget(callable_or_coro: AsyncCallable, *args, **kwargs) -> Optional[asyncio.Task]:
    """
    Schedule an async side effect to run after the current request returns.

    Accepts either an async callable (a coroutine function that we'll await
    after calling it with args/kwargs) or an already-constructed coroutine
    object (in which case args/kwargs must be empty).

    Errors raised by the dispatched callable are logged but never propagated
    to the caller. Side effects must not affect request success.

    Returns the Task handle (mostly for tests / debugging). The caller
    SHOULD NOT await this — that defeats the entire point.

    Usage:

        # async function reference + args
        fire_and_forget(invalidate_posters, system_id, galaxy)

        # already-constructed coroutine (e.g. from a wrapper)
        fire_and_forget(do_async_work())

    For sync callables (e.g., db.add_activity_log), the handler should
    accept `background_tasks: BackgroundTasks` and call
    `background_tasks.add_task(fn, ...)` directly. Don't try to wrap a sync
    function in this helper — asyncio.create_task() requires a coroutine.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # No running loop — we're being called from a sync context outside a
        # request. Run the coroutine to completion synchronously rather than
        # silently dropping it. This path is mostly hit by tests/CLIs.
        logger.warning("fire_and_forget called outside a running event loop; running synchronously")
        try:
            if inspect.iscoroutine(callable_or_coro):
                asyncio.run(_safe_await(callable_or_coro))
            elif callable(callable_or_coro):
                asyncio.run(_safe_call(callable_or_coro, *args, **kwargs))
            else:
                logger.warning(f"fire_and_forget given non-callable: {type(callable_or_coro)!r}")
        except Exception as e:
            logger.warning(f"fire_and_forget sync fallback failed: {e}")
        return None

    if inspect.iscoroutine(callable_or_coro):
        if args or kwargs:
            logger.warning(
                "fire_and_forget: ignoring args/kwargs passed alongside an already-constructed coroutine"
            )
        coro = _safe_await(callable_or_coro)
    elif callable(callable_or_coro):
        coro = _safe_call(callable_or_coro, *args, **kwargs)
    else:
        logger.warning(f"fire_and_forget given non-callable, non-coroutine: {type(callable_or_coro)!r}")
        return None

    task = loop.create_task(coro)
    # Keep a strong reference so the task isn't GC'd mid-flight
    _running_tasks.add(task)
    task.add_done_callback(_running_tasks.discard)
    return task


_running_tasks: "set[asyncio.Task]" = set()


async def _safe_await(coro: Coroutine[Any, Any, Any]) -> None:
    """Await a coroutine and swallow any exception with a WARNING log."""
    try:
        await coro
    except Exception as e:
        logger.warning(f"Background side effect failed: {e}", exc_info=True)


async def _safe_call(fn: Callable[..., Awaitable[Any]], *args, **kwargs) -> None:
    """Call an async function and swallow any exception with a WARNING log."""
    try:
        result = fn(*args, **kwargs)
        if inspect.isawaitable(result):
            await result
    except Exception as e:
        logger.warning(f"Background side effect failed in {getattr(fn, '__name__', fn)!r}: {e}", exc_info=True)


def pending_task_count() -> int:
    """Return the number of currently-running fire_and_forget tasks. Used by tests."""
    return len(_running_tasks)
