"""Retry helper shared by all remote fetches."""

import time
from collections.abc import Callable


class FetchError(Exception):
    """A remote fetch failed after all retries."""

    def __init__(self, source: str, reason: str) -> None:
        super().__init__(f"{source}: {reason}")
        self.source = source
        self.reason = reason


def with_retries[T](
    fn: Callable[[], T],
    source: str,
    *,
    attempts: int = 5,
    base_delay: float = 2.0,
    sleep: Callable[[float], None] = time.sleep,
) -> T:
    """Call `fn`, retrying with exponential backoff (2, 4, 8, 16 s by default).

    The delays are deterministic so a run is reproducible.
    """
    for attempt in range(attempts):
        try:
            return fn()
        except Exception as exc:
            if attempt == attempts - 1:
                raise FetchError(source, f"{type(exc).__name__}: {exc}") from exc
            sleep(base_delay * 2**attempt)
    raise AssertionError("unreachable")
