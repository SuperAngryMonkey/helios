# 0003 — Polling cadences

Date: 2026-06-04 · Status: Accepted

## Context

The Wanderer exposes three categories of data with very different rates
of change. We must pick a polling cadence that captures enough signal
without flooding Postgres or the controller.

## Categories

1. **Real-time** — SOC, voltages, currents, charging state, faults.
   Change continuously throughout the day.
2. **Daily counters** — Wh generated/consumed today, voltage min/max,
   peak power. Reset by the controller at controller-local midnight.
3. **Lifetime counters** — operating days, cumulative Ah/Wh. Increment
   slowly, never reset.

## Decision

- Real-time + state + faults: **30 seconds**.
- Daily counters: **5 minutes**, upsert by `CURRENT_DATE`.
- Lifetime counters: **1 hour**.

## Rationale

### Real-time at 30 s

- Battery dynamics: a 30 s sample is fine-grained enough to catch MPPT
  hunt, load transients, and dawn/dusk transitions.
- Storage: 2,880 rows/day × 365 = ~1.05 M/year. Plain Postgres handles
  this without TimescaleDB.
- Modbus round-trip is ~50 ms per read; the controller is idle for
  99.8% of each cycle.

### Daily at 5 min

- The daily counters update continuously throughout the day. We want a
  current value visible on the dashboard.
- 5 min × 288 polls/day = 288 upserts/day per row. Cheap.
- Upsert by date means we only ever have one row per day.

### Lifetime at 1 h

- Counters change slowly (days, kWh). Hourly is more than enough
  resolution for trending.
- 24 rows/day × 365 = 8,760 rows/year. Tiny.
- Hourly snapshots let us detect counter resets (firmware update,
  factory reset) without missing too much history.

### Faults

- Polled every real-time cycle but only inserted into `events` when the
  bitfield **changes**. Idle state writes nothing.

## Trade-offs

- 30 s is conservative; some setups poll Renogy controllers every 10 s.
  Easy to dial up via `HELIOS_REALTIME_SEC` in `/etc/helios/controller.env`.
- Daily counters polled at 5 min could miss the last data point of a day
  if the controller resets between 23:55:00 and 00:00:00 local. The
  lifetime counters serve as a backup.

## Consequences

- All three cadences are environment-variable configurable.
- "First cycle fires everything at once" behavior is intentional —
  fresh restarts always capture a full snapshot immediately.
