# 0005 — Dashboard chart expansion (v0.3.0)

Date: 2026-06-19 · Status: Accepted

## Context

v0.1.0 shipped two timeseries charts (power flows, battery voltage) and
four realtime metric tiles. Sufficient for a first-pass "is it working"
dashboard, but doesn't tell the operator much about longer-term system
behavior, thermal margin, or event history.

v0.3.0 expands the dashboard to a full operator's view.

## Charts added

1. **Battery SOC (24h)** — line, green. Same shape as battery voltage
   but easier to read at a glance.
2. **Charge current (24h)** — line, cyan. Verifies the charge profile
   (bulk → absorb → float) and catches over-current.
3. **Temperatures (24h)** — two lines. Controller (cyan) and battery
   (green — from the battery temp probe). Alerts visually if either
   runs hot.
4. **Charge state (24h)** — horizontal band of color-coded 5-min buckets
   showing when the controller was in each state (deactivated,
   activated, MPPT, equalizing, boost, floating, current_limit).
5. **7-day energy** — grouped bar chart, generated Wh (cyan) vs
   consumed Wh (orange). The decision-driving chart: net-positive or
   net-negative trend at a glance.
6. **Faults (30d)** — sparse scatter timeline of fault events. Red
   points for each non-zero fault; latest 5 listed below with
   timestamp and description. Badge switches between "CLEAR" and
   "N EVENTS".

## Data model

All charts pull from existing tables — no schema changes.

- `telemetry` — 5-min buckets from the `/api/timeseries` endpoint,
  extended in v0.3.0 to include `charge_i`, `battery_temp_c`,
  `controller_temp_c`, and `charge_state`.
- `daily` — 7-day query for the energy bar chart.
- `events` — 30-day query for the fault timeline.

### Aggregation of `charge_state`

`avg()` doesn't make semantic sense on a discrete enum, so the query
uses PostgreSQL's `mode() WITHIN GROUP (ORDER BY charge_state)` —
returning the most common state per 5-min bucket. This is accurate
for stable states (MPPT for 5 minutes → mppt) and gracefully picks a
representative for transition buckets.

## Bucketing

All timeseries queries use `hours * 3600 / 288` seconds per bucket,
which for 24 hours resolves to **5-minute buckets**. This gives 288
data points per 24h — dense enough for smooth lines, sparse enough
that the JSON payload stays under 100 KB and Chart.js updates stay
fast (~5 ms per chart on modern browsers).

## Charge state color palette

| State | Color | Rationale |
|---|---|---|
| deactivated | txt3 (grey) | Idle, no comment |
| activated | acc2 (orange) | Awake but not charging — noticeable |
| mppt | acc3 (green) | Optimal harvest, best state |
| equalizing | acc (cyan) | Rare, informational |
| boost | acc (cyan) | Rare, informational |
| floating | acc3b (muted green) | Full, holding — good but done |
| current_limit | danger (red) | Something's wrong or panel is oversized |

## Refresh cadence

All charts refresh on the same 30-second interval as the realtime
tiles, driven by a single `Promise.all` of five endpoints. On a 24h
window that's ~1 update per bucket, matching the daemon's poll rate.

## Consequences

- The API payload per refresh grows from ~30 KB to ~60 KB. Fine for
  desktop and phone.
- No new client dependencies. Chart.js 4 + chartjs-adapter-date-fns
  handle everything.
- Chart initialization moved from inline code to a `line()` helper
  and a `baseTimeOpts()` factory to avoid repetition across the six
  new charts.
- The dashboard is longer — expect to scroll on a phone. Considered
  breaking `/faults` and `/history` into separate pages but kept
  everything on one page for the "single glance" pattern. Split later
  if the page becomes unwieldy.

## Deferred

- **Range picker** — 24h / 7d / 30d / custom on the timeseries charts.
  Grafana-like. Meaningful but adds complexity; defer to v0.4.x.
- **Alerting from faults** — the timeline shows history but doesn't
  push notifications. Deferred to a separate ADR (0006 reserved).
- **Threshold-based tile colors** — SOC/V tiles still hard-coded green
  in the template. Small JS change, deferred to a v0.3.x point release.
