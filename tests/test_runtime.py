"""Plain-Python replacements for Streamlit's caching and notifications (expenses.runtime)."""

import logging

from expenses import runtime


def test_cache_data_memoizes_until_ttl(monkeypatch):
    calls = []
    now = [100.0]
    monkeypatch.setattr(runtime.time, "monotonic", lambda: now[0])

    @runtime.cache_data(ttl=10)
    def load(x):
        calls.append(x)
        return x * 2

    assert load(2) == 4 and load(2) == 4
    assert calls == [2]  # second call served from the cache
    assert load(3) == 6 and calls == [2, 3]  # different args, different entry
    now[0] += 11  # past the TTL
    assert load(2) == 4 and calls == [2, 3, 2]


def test_clear_caches_drops_cache_data_entries():
    calls = []

    @runtime.cache_data(ttl=600)
    def load():
        calls.append(1)
        return len(calls)

    assert load() == 1 and load() == 1
    runtime.clear_caches()
    assert load() == 2


def test_cache_resource_is_a_singleton_not_cleared():
    created = []

    @runtime.cache_resource
    def engine(name="x"):
        created.append(name)
        return object()

    first = engine()
    assert engine() is first
    runtime.clear_caches()  # resources (connection pools) survive a data-cache bust
    assert engine() is first and created == ["x"]


def test_notify_error_and_warning_log(caplog):
    with caplog.at_level(logging.WARNING, logger="expenses"):
        runtime.notify_error("db down")
        runtime.notify_warning("slow")
    levels = {(r.levelname, r.getMessage()) for r in caplog.records}
    assert ("ERROR", "db down") in levels
    assert ("WARNING", "slow") in levels
