"""On-disk response cache + per-provider token-bucket rate limiter.

Cache dir resolution (read-only env probing, no network):
  1. ``$CODEX_HOME/omr/cache``
  2. ``$HOME/.codex/omr/cache``        (POSIX)
  3. ``%USERPROFILE%\\.codex\\omr\\cache`` (Windows)

Entries are JSON files keyed by ``sha256(provider + "\\x00" + normalized_query)``.
TTL is 14 days. A *pinned fixture* is honored: any pre-existing cache file
(regardless of its stored timestamp) is treated as a valid offline answer
when its ``"pinned"`` flag is true OR when it is still within TTL. This lets
AC4 run fully offline against checked-in fixtures.
"""

from __future__ import annotations

import hashlib
import json
import os
import random
import threading
import time

from .normalize import normalize_title

__all__ = [
    "cache_dir",
    "cache_key",
    "CacheStore",
    "TokenBucket",
    "RateLimiterRegistry",
    "backoff_delays",
]

TTL_SECONDS = 14 * 24 * 60 * 60  # 14 days


def cache_dir() -> str:
    """Resolve (and lazily create) the on-disk cache directory."""
    codex_home = os.environ.get("CODEX_HOME")
    if codex_home:
        base = codex_home
    else:
        home = os.environ.get("HOME") or os.environ.get("USERPROFILE") or os.path.expanduser("~")
        base = os.path.join(home, ".codex")
    path = os.path.join(base, "omr", "cache")
    os.makedirs(path, exist_ok=True)
    return path


def cache_key(provider: str, query: str) -> str:
    """sha256 over provider + normalized query (stable / deterministic)."""
    norm = normalize_title(query)
    raw = f"{provider}\x00{norm}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


class CacheStore:
    """Tiny JSON file cache. No network, no third-party deps."""

    def __init__(self, directory: str | None = None) -> None:
        self._dir = directory or cache_dir()

    def _path(self, provider: str, query: str) -> str:
        return os.path.join(self._dir, cache_key(provider, query) + ".json")

    def get(self, provider: str, query: str):
        """Return cached payload or ``None``.

        A fixture is honored when ``pinned`` is truthy regardless of age;
        otherwise the 14-day TTL applies.
        """
        path = self._path(provider, query)
        try:
            with open(path, "r", encoding="utf-8") as fh:
                doc = json.load(fh)
        except (OSError, ValueError):
            return None
        if not isinstance(doc, dict):
            return None
        if doc.get("pinned"):
            return doc.get("payload")
        ts = doc.get("ts")
        if not isinstance(ts, (int, float)):
            return None
        if (time.time() - ts) > TTL_SECONDS:
            return None
        return doc.get("payload")

    def set(self, provider: str, query: str, payload, pinned: bool = False) -> None:
        path = self._path(provider, query)
        doc = {
            "provider": provider,
            "query": query,
            "ts": time.time(),
            "pinned": bool(pinned),
            "payload": payload,
        }
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(doc, fh, ensure_ascii=False)
        os.replace(tmp, path)


class TokenBucket:
    """Thread-safe token bucket. ``rate`` tokens/sec, burst ``capacity``."""

    def __init__(self, rate: float, capacity: float | None = None) -> None:
        self.rate = float(rate)
        self.capacity = float(capacity if capacity is not None else max(1.0, rate))
        self._tokens = self.capacity
        self._last = time.monotonic()
        self._lock = threading.Lock()

    def acquire(self, tokens: float = 1.0, sleep=time.sleep) -> float:
        """Block until ``tokens`` are available. Returns waited seconds."""
        waited = 0.0
        while True:
            with self._lock:
                now = time.monotonic()
                elapsed = now - self._last
                self._last = now
                self._tokens = min(self.capacity, self._tokens + elapsed * self.rate)
                if self._tokens >= tokens:
                    self._tokens -= tokens
                    return waited
                deficit = tokens - self._tokens
                wait_for = deficit / self.rate if self.rate > 0 else 0.05
            sleep(wait_for)
            waited += wait_for


class RateLimiterRegistry:
    """Per-provider conservative limiters (Crossref/OpenAlex <= ~3 req/s)."""

    _DEFAULTS = {
        "crossref": 3.0,
        "openalex": 3.0,
        "europepmc": 3.0,
        "semanticscholar": 1.0,
    }

    def __init__(self, overrides: dict | None = None) -> None:
        rates = dict(self._DEFAULTS)
        if overrides:
            rates.update(overrides)
        self._buckets = {p: TokenBucket(r) for p, r in rates.items()}

    def acquire(self, provider: str, sleep=time.sleep) -> float:
        bucket = self._buckets.get(provider)
        if bucket is None:
            bucket = self._buckets[provider] = TokenBucket(1.0)
        return bucket.acquire(sleep=sleep)


def backoff_delays(max_retries: int = 5, base: float = 0.5,
                    rng: random.Random | None = None):
    """Yield exponential-backoff-with-jitter delays for 429/503 retries."""
    r = rng or random.Random()
    for attempt in range(max_retries):
        ceiling = base * (2 ** attempt)
        yield r.uniform(0.0, ceiling)
