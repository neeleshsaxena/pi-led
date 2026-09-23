"""Shared test fixtures for the flights budget suite.

Everything here keeps tests hermetic: the API key is a dummy, the HTTP client is
a call-counting fake (never touches the network — that would spend the very units
we're protecting), and `time.monotonic` is a hand-advanced fake clock so we can
fast-forward hours/days deterministically.
"""
from __future__ import annotations

import httpx
import pytest
import pytest_asyncio

import apps.flights.flights as flights_mod
from apps.flights.flights import FlightsClient


class FakeClock:
    """A `monotonic()` stand-in whose value we advance by hand."""

    def __init__(self, start: float = 1000.0) -> None:
        self.now = float(start)

    def tick(self, seconds: float) -> None:
        self.now += float(seconds)


class _FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


class FakeHTTP:
    """Stands in for FlightsClient._client. Counts `.get()` calls and never hits
    the network. Returns a canned board, or raises to simulate an API failure."""

    def __init__(self, payload: dict | None = None, fail: bool = False) -> None:
        self.calls = 0
        self.payload = payload if payload is not None else {"departures": [], "arrivals": []}
        self.fail = fail

    async def get(self, url, params=None, headers=None):
        self.calls += 1
        if self.fail:
            raise httpx.ConnectError("simulated API failure")
        return _FakeResponse(self.payload)

    async def aclose(self) -> None:
        return None


@pytest.fixture
def clock(monkeypatch) -> FakeClock:
    """Patch the flights module's monotonic clock with a hand-advanced fake."""
    c = FakeClock()
    monkeypatch.setattr(flights_mod.time, "monotonic", lambda: c.now)
    return c


@pytest_asyncio.fixture
async def make_client(monkeypatch, clock):
    """Factory: `await make_client(...) -> (FlightsClient, FakeHTTP)`.

    The AeroDataBox key is stubbed present, the real httpx client is discarded and
    replaced with a FakeHTTP counter, and every client is closed on teardown.
    """
    monkeypatch.setenv("AERODATABOX_API_KEY", "dummy-test-key")
    monkeypatch.delenv("RAPIDAPI_KEY", raising=False)
    created: list[FlightsClient] = []

    async def _make(payload=None, fail=False, ttl=100.0, retry_interval=30.0):
        c = FlightsClient(ttl=ttl, retry_interval=retry_interval)
        await c._client.aclose()  # drop the real httpx client (unused in tests)
        fake = FakeHTTP(payload=payload, fail=fail)
        c._client = fake  # all HTTP now flows through the counter
        created.append(c)
        return c, fake

    yield _make
    for c in created:
        await c.close()
