"""Unit tests for FlightsClient._shape: past-flight drop, tier/time sort, delay
computation, and graceful handling of missing/partial nodes. No network."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone


def _node(dt: datetime) -> dict:
    """An AeroDataBox time node, as the API returns it."""
    return {
        "utc": dt.strftime("%Y-%m-%d %H:%MZ"),
        "local": dt.strftime("%Y-%m-%d %H:%M+00:00"),
    }


def _flight(number: str, iata: str, sched: datetime, revised: datetime | None = None,
            name: str = "Air X") -> dict:
    mv = {"scheduledTime": _node(sched), "airport": {"iata": iata, "name": f"{iata} City"}}
    if revised is not None:
        mv["revisedTime"] = _node(revised)
    return {"number": number, "airline": {"name": name}, "movement": mv}


async def test_shape_drops_past_flights(make_client):
    client, _ = await make_client()
    now = datetime(2026, 9, 17, 12, 0, tzinfo=timezone.utc)
    flights = [
        _flight("AA1", "LAX", now - timedelta(minutes=30)),  # already departed -> drop
        _flight("AA2", "JFK", now + timedelta(minutes=30)),  # upcoming -> keep
    ]
    out = client._shape(flights, "DEP", now)
    assert [f["number"] for f in out] == ["AA2"]


async def test_shape_tier_then_time_sort(make_client):
    client, _ = await make_client()
    now = datetime(2026, 9, 17, 12, 0, tzinfo=timezone.utc)
    flights = [
        _flight("D1", "SEA", now + timedelta(minutes=10)),  # domestic, soonest
        _flight("T1", "LHR", now + timedelta(minutes=90)),  # TOP (Europe), later
        _flight("I1", "YYZ", now + timedelta(minutes=20)),  # international
        _flight("T2", "DEL", now + timedelta(minutes=60)),  # TOP (India), sooner than T1
    ]
    out = client._shape(flights, "DEP", now)
    # TOP tier first (soonest within tier), then international, then domestic.
    assert [f["number"] for f in out] == ["T2", "T1", "I1", "D1"]


async def test_shape_delay_and_minutes_use_revised(make_client):
    client, _ = await make_client()
    now = datetime(2026, 9, 17, 12, 0, tzinfo=timezone.utc)
    sched = now + timedelta(minutes=30)
    revised = sched + timedelta(minutes=15)  # 15-min delay
    out = client._shape([_flight("X1", "LHR", sched, revised=revised)], "DEP", now)
    assert out[0]["delay_min"] == 15
    assert out[0]["minutes"] == 45  # minutes-until uses the effective (revised) time


async def test_shape_handles_missing_nodes(make_client):
    client, _ = await make_client()
    now = datetime(2026, 9, 17, 12, 0, tzinfo=timezone.utc)
    flights = [
        {"number": "N1"},                        # no movement at all
        {"number": "N2", "movement": {}},        # movement, no times
        {"number": "N3", "movement": {"scheduledTime": None}},  # None time node
        _flight("OK", "LHR", now + timedelta(minutes=30)),      # the only valid one
    ]
    out = client._shape(flights, "DEP", now)  # must not raise
    assert [f["number"] for f in out] == ["OK"]


async def test_shape_empty_input(make_client):
    client, _ = await make_client()
    now = datetime(2026, 9, 17, 12, 0, tzinfo=timezone.utc)
    assert client._shape(None, "DEP", now) == []
    assert client._shape([], "ARR", now) == []
