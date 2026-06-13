"""Helpers for running async code from sync pipeline stages."""

import asyncio
import concurrent.futures
from collections.abc import Coroutine
from typing import TypeVar

T = TypeVar("T")

# Shared executor for nested async work when an event loop is already running.
_EXECUTOR = concurrent.futures.ThreadPoolExecutor(max_workers=4, thread_name_prefix="async-bridge")


def run_coroutine_sync(coro: Coroutine[None, None, T]) -> T:
    """Run a coroutine from sync code, including when a loop is already active."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    future = _EXECUTOR.submit(asyncio.run, coro)
    return future.result()
