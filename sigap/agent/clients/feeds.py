"""Fetching public feeds: one GET, one cache, one way to fail.

Every outside source SIGAP reads without a credential (GDACS, NASA EONET, USGS,
Open-Meteo, Google News, Frankfurter, Nager.Date) comes through here, so the
three rules are kept in one place rather than once per feed:

  - A feed is asked politely: a named User-Agent, a timeout, and a cache, so a
    watcher that runs every few minutes does not hammer a public service.
    GDACS takes 15 to 50 seconds to answer; asking it every sweep would make
    every sweep that slow.
  - A cached copy keeps the time it was really fetched. A caller labels it with
    that time, never with the time it was read from memory, so a figure that is
    twenty minutes old says so.
  - A failure is a FeedError, which the caller turns into Origin.MISSING. A
    feed that cannot be reached is not a feed that says all is well. A failure
    is remembered for a few minutes, so a feed that is timing out costs one
    timeout, not one per tool call that asks for it.
"""
from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

#: Who is asking. Several of these feeds refuse urllib's default agent string.
USER_AGENT = "SIGAP/0.1 (supply disruption response; +https://github.com/maulana-tech/socrates)"


class FeedError(RuntimeError):
    """The feed did not give a usable answer: unreachable, slow, or malformed."""


_LOCK = threading.Lock()
#: url -> (fetched_at, body). The largest body, GDACS's RSS file, is about 1 MB.
_CACHE: Dict[str, Tuple[datetime, Any]] = {}
#: url -> (failed_at, reason).
_FAILED: Dict[str, Tuple[datetime, str]] = {}
#: How long a failed feed is left alone before it is asked again.
RETRY_AFTER = 300


def _fetch(url: str, timeout: float, headers: Optional[Dict[str, str]]) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT,
                                               "Accept": "*/*", **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        raise FeedError(f"{url.split('?')[0]} answered HTTP {e.code}") from None
    except Exception as e:                                           # noqa: BLE001
        raise FeedError(f"{url.split('?')[0]}: {type(e).__name__}: {e}") from None


def get(url: str, *, ttl: float, timeout: float = 20, as_json: bool = True,
        headers: Optional[Dict[str, str]] = None) -> Tuple[Any, datetime]:
    """(body, fetched_at). Served from the cache while younger than `ttl`
    seconds. Two callers asking for the same URL at once may both fetch; that
    costs one extra request and keeps a slow feed from holding the lock."""
    now = datetime.now(timezone.utc)
    with _LOCK:
        hit, failed = _CACHE.get(url), _FAILED.get(url)
    if hit and (now - hit[0]).total_seconds() < ttl:
        return hit[1], hit[0]
    if failed and (now - failed[0]).total_seconds() < min(ttl, RETRY_AFTER):
        raise FeedError(f"{failed[1]} (at {failed[0]:%H:%M} UTC; not retried yet)")
    try:
        raw = _fetch(url, timeout, headers)
        try:
            body = json.loads(raw.decode("utf-8")) if as_json else raw.decode("utf-8", "replace")
        except ValueError as e:
            raise FeedError(f"{url.split('?')[0]} did not return JSON: {e}") from None
    except FeedError as e:
        with _LOCK:
            _FAILED[url] = (now, str(e))
        raise
    with _LOCK:
        _CACHE[url] = (now, body)
        _FAILED.pop(url, None)
    return body, now


def prime(url: str, body: Any, fetched_at: Optional[datetime] = None) -> None:
    """Put a recorded answer in the cache. The self-checks use it to run every
    parser offline on a real payload."""
    with _LOCK:
        _CACHE[url] = (fetched_at or datetime.now(timezone.utc), body)
        _FAILED.pop(url, None)


def forget(url: Optional[str] = None) -> None:
    with _LOCK:
        if url is None:
            _CACHE.clear()
            _FAILED.clear()
        else:
            _CACHE.pop(url, None)
            _FAILED.pop(url, None)


def age_note(fetched_at: datetime) -> str:
    """'fetched 12 min ago' for a Result note; empty when it was just fetched."""
    secs = (datetime.now(timezone.utc) - fetched_at).total_seconds()
    return f"fetched {int(secs // 60)} min ago" if secs >= 60 else ""


def demo() -> None:
    url = "https://example.invalid/feed.json"
    then = datetime(2026, 10, 24, 0, 0, tzinfo=timezone.utc)
    prime(url, {"ok": True}, then)
    body, at = get(url, ttl=10**9)
    assert body == {"ok": True} and at == then, "a cached copy keeps its real fetch time"
    forget(url)
    try:
        get(url, ttl=60, timeout=3)
        raise AssertionError("an unreachable feed must raise FeedError")
    except FeedError as e:
        assert "example.invalid" in str(e)
    started = time.time()
    try:
        get(url, ttl=60, timeout=3)
        raise AssertionError("a feed that just failed must still fail")
    except FeedError as e:
        assert "not retried yet" in str(e) and time.time() - started < 0.5, \
            "a feed that just failed is not asked again straight away"
    forget(url)
    print("feeds ok: cache keeps fetch time ✓ · unreachable feed raises FeedError ✓ "
          "· a failure is not retried at once ✓")


if __name__ == "__main__":
    demo()
