"""Budget-safety tests for the AeroDataBox flight board.

These lock in the guarantee that the panel cannot exhaust the free-tier quota
(600 API units/month, ~2 units per airport call). Every test fakes HTTP — nothing
here ever touches the real API — and drives a hand-advanced fake clock so a full
day (or month) of rendering runs in milliseconds.

The invariant under test: `board()` makes at most ONE network call per TTL window
no matter how often it is called, and failures are retry-throttled, so the steady
state is ~8 fetches/day (~480 units/month).
"""
from __future__ import annotations


async def test_many_renders_one_fetch(make_client, clock):
    """The money test: 300 render frames within one TTL => exactly ONE HTTP call.

    This is the direct guard against the original bug (cache keyed by a per-minute
    window, which defeated the TTL and drained the whole month in days)."""
    client, fake = await make_client(ttl=10800.0, retry_interval=1800.0)
    for _ in range(300):
        clock.tick(0.2)  # ~5 fps; 300 frames = 60s of continuous rendering
        await client.board("KSFO")
    assert fake.calls == 1


async def test_first_fetch_not_throttled_after_boot(make_client, clock):
    """Regression for the `_last_attempt` init bug.

    time.monotonic() is seconds-since-boot on Linux, so a freshly-booted Pi starts
    at mono~=25. With `_last_attempt = 0.0` the first render saw (25 - 0) < 1800 and
    wrongly throttled the initial fetch — flights stayed blank for ~30 min after
    every reboot. `_last_attempt = -inf` must let the first attempt through."""
    clock.now = 25.0  # emulate 25 seconds of uptime (< retry_interval)
    client, fake = await make_client(ttl=10800.0, retry_interval=1800.0)
    await client.board("KSFO")
    assert fake.calls == 1  # would be 0 (throttled) under the old _last_attempt=0.0


async def test_ttl_expiry_refetches_once(make_client, clock):
    """Within the TTL the board is served from cache; once past it, exactly one
    more call, then cached again."""
    client, fake = await make_client(ttl=100.0, retry_interval=30.0)
    await client.board("KSFO")
    assert fake.calls == 1

    clock.tick(50)  # still inside the 100s TTL
    await client.board("KSFO")
    assert fake.calls == 1

    clock.tick(60)  # 110s since the first fetch => TTL expired
    await client.board("KSFO")
    assert fake.calls == 2

    clock.tick(10)  # fresh cache again
    await client.board("KSFO")
    assert fake.calls == 2


async def test_failure_is_throttled(make_client, clock):
    """A persistent API failure must be retried at most once per retry_interval,
    serving an empty board in between — never a 5 fps storm of requests/429s."""
    client, fake = await make_client(fail=True, ttl=100.0, retry_interval=30.0)
    for _ in range(200):
        clock.tick(0.1)  # 20s total, all inside the 30s retry window
        res = await client.board("KSFO")
        assert res == {"departures": [], "arrivals": []}
    assert fake.calls == 1  # only the very first attempt actually hit HTTP

    clock.tick(30)  # past the retry interval => exactly one more attempt
    await client.board("KSFO")
    assert fake.calls == 2


async def test_failure_then_recovery_serves_last_good(make_client, clock):
    """After a good fetch, a later transient failure serves the last-good board
    (not empty) and stays throttled."""
    # Far-future scheduledTime so the flight survives _shape's past-flight drop
    # regardless of the real wall clock when the test runs.
    good = {
        "departures": [{
            "number": "UA1",
            "airline": {"name": "United"},
            "movement": {
                "scheduledTime": {"utc": "2099-01-01 12:00Z", "local": "2099-01-01 04:00-08:00"},
                "airport": {"iata": "LHR", "name": "London Heathrow"},
            },
        }],
        "arrivals": [],
    }
    client, fake = await make_client(payload=good, ttl=100.0, retry_interval=30.0)
    first = await client.board("KSFO")
    assert fake.calls == 1
    assert [f["number"] for f in first["departures"]] == ["UA1"]  # kept + shaped

    # TTL expires; flip the fake to failing and advance past both TTL and throttle.
    clock.tick(200)
    fake.fail = True
    res = await client.board("KSFO")
    assert fake.calls == 2  # it retried (TTL gone, throttle clear)
    assert res == first  # served the last-good board rather than empty


async def test_no_key_no_network(monkeypatch, make_client):
    """With no key, board() returns empty and makes ZERO network calls."""
    client, fake = await make_client(ttl=100.0, retry_interval=30.0)
    monkeypatch.delenv("AERODATABOX_API_KEY", raising=False)
    monkeypatch.delenv("RAPIDAPI_KEY", raising=False)
    assert client.has_key is False
    res = await client.board("KSFO")
    assert res == {"departures": [], "arrivals": []}
    assert fake.calls == 0


async def test_24h_continuous_render_under_daily_ceiling(make_client, clock):
    """A full day of continuous (worst-case) rendering stays at the ~8-fetch/day
    ceiling => <=18 units/day."""
    client, fake = await make_client(ttl=10800.0, retry_interval=1800.0)
    step = 5.0
    for _ in range(int(24 * 3600 / step)):
        await client.board("KSFO")
        clock.tick(step)
    assert fake.calls <= 9  # 24h / 3h TTL = 8 windows, +1 boundary at most
    assert fake.calls * 2 <= 18  # units/day


async def test_30day_projection_stays_under_600_units(make_client, clock):
    """30 days of continuous rendering must stay well under the 600-unit cap.

    Sampled at 5-minute steps: 300s << retry_interval (1800) << TTL (10800), so
    every TTL boundary is still crossed exactly — the fetch count is faithful."""
    client, fake = await make_client(ttl=10800.0, retry_interval=1800.0)
    step = 300.0
    for _ in range(int(30 * 24 * 3600 / step)):
        await client.board("KSFO")
        clock.tick(step)
    units = fake.calls * 2
    assert fake.calls <= 30 * 8 + 1  # ~240-241 fetches
    assert units < 600  # the whole point: a month of rendering < the cap
