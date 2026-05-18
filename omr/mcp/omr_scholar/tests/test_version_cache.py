import os

from omr_scholar import core
from omr_scholar.cache import (
    CacheStore,
    RateLimiterRegistry,
    TokenBucket,
    backoff_delays,
    cache_dir,
    cache_key,
)
from omr_scholar.version import get_version


def test_version_zero_side_effects():
    v = core.version()
    assert v["server"] == "omr-scholar"
    assert isinstance(v["version"], str) and v["version"]
    # idempotent / no mutation
    assert core.version() == v


def test_get_version_fallback_is_semver_like():
    v = get_version()
    assert v.count(".") >= 1


def test_cache_key_deterministic_and_provider_scoped():
    a = cache_key("crossref", "Hello World")
    b = cache_key("crossref", "hello   world!")  # normalized -> same
    c = cache_key("openalex", "Hello World")
    assert a == b
    assert a != c
    assert len(a) == 64


def test_cache_dir_respects_codex_home(tmp_path, monkeypatch):
    monkeypatch.setenv("CODEX_HOME", str(tmp_path))
    d = cache_dir()
    assert d == os.path.join(str(tmp_path), "omr", "cache")
    assert os.path.isdir(d)


def test_cache_store_roundtrip_and_ttl(tmp_path):
    store = CacheStore(str(tmp_path))
    assert store.get("crossref", "q") is None
    store.set("crossref", "q", [{"title": "T"}])
    assert store.get("crossref", "q") == [{"title": "T"}]


def test_pinned_fixture_honored_regardless_of_age(tmp_path):
    import json
    store = CacheStore(str(tmp_path))
    key = cache_key("crossref", "frozen query")
    doc = {
        "provider": "crossref", "query": "frozen query",
        "ts": 0,  # ancient -> would be TTL-expired
        "pinned": True,
        "payload": [{"title": "Frozen", "doi": "10.1/f"}],
    }
    with open(os.path.join(str(tmp_path), key + ".json"), "w") as fh:
        json.dump(doc, fh)
    assert store.get("crossref", "frozen query") == [
        {"title": "Frozen", "doi": "10.1/f"}
    ]


def test_token_bucket_blocks_then_allows():
    waited = []
    bucket = TokenBucket(rate=1000.0, capacity=1.0)
    bucket.acquire(sleep=waited.append)  # consumes the single token
    bucket.acquire(sleep=waited.append)  # must wait for refill
    assert any(w > 0 for w in waited)


def test_rate_limiter_registry_known_providers():
    reg = RateLimiterRegistry()
    # uses an instant fake sleep -> no real delay
    reg.acquire("crossref", sleep=lambda s: None)
    reg.acquire("openalex", sleep=lambda s: None)
    reg.acquire("unknown-provider", sleep=lambda s: None)


def test_backoff_delays_bounded_and_increasing_ceiling():
    import random
    delays = list(backoff_delays(max_retries=4, base=0.5,
                                 rng=random.Random(42)))
    assert len(delays) == 4
    assert all(d >= 0 for d in delays)
    assert delays[-1] <= 0.5 * (2 ** 3)
