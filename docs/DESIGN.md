# Design

## Architecture

```
controller → gateway → daemon → postgres → web → browser
```

The split is intentional: the daemon owns the Modbus interaction, the
database is the contract, and the web app is a thin reader. Any one of
those layers can be replaced without touching the others.

## Why Modbus RTU over raw TCP

The Wanderer speaks Modbus RTU on its RJ12 RS-232 port at 9600 8N1. The
EarthCam serial gateway re-emits those bytes verbatim onto a TCP socket.
That's **not** Modbus TCP (which has its own MBAP header and lives on
port 502); it's RTU frames carried as raw TCP payload.

pymodbus handles this with `ModbusTcpClient(framer=FramerType.RTU)` — the
TCP transport with the RTU framer. See [ADR-0001](decisions/0001-modbus-rtu-over-tcp.md)
for the alternatives we rejected.

## Register map

Wanderer holding registers used by helios:

| Addr | Count | Field | Scale |
|------|-------|-------|-------|
| 0x0100 | 1 | Battery SOC | % |
| 0x0101 | 1 | Battery voltage | × 0.1 V |
| 0x0102 | 1 | Battery charge current | × 0.01 A |
| 0x0103 | 1 | Temp word: high byte = controller °C, low byte = battery °C (signed) | — |
| 0x0104 | 1 | Load voltage | × 0.1 V |
| 0x0105 | 1 | Load current | × 0.01 A |
| 0x0106 | 1 | Load power | W |
| 0x0107 | 1 | PV voltage | × 0.1 V |
| 0x0108 | 1 | PV current | × 0.01 A |
| 0x0109 | 1 | PV power | W |
| 0x010B | 1 | Today battery V min | × 0.1 V |
| 0x010C | 1 | Today battery V max | × 0.1 V |
| 0x010D | 1 | Today max charge current | × 0.01 A |
| 0x010E | 1 | Today max discharge current | × 0.01 A |
| 0x010F | 1 | Today max charge power | W |
| 0x0110 | 1 | Today max discharge power | W |
| 0x0111 | 1 | Today charge Ah | Ah |
| 0x0112 | 1 | Today discharge Ah | Ah |
| 0x0113 | 1 | Today generation Wh | Wh |
| 0x0114 | 1 | Today consumption Wh | Wh |
| 0x0115 | 1 | Total operating days | days |
| 0x0116 | 1 | Total over-discharges | count |
| 0x0117 | 1 | Total full charges | count |
| 0x0118 | 2 | Cumulative charge Ah (big-endian 32-bit) | Ah |
| 0x011A | 2 | Cumulative discharge Ah | Ah |
| 0x011C | 2 | Cumulative generation Wh | Wh |
| 0x011E | 2 | Cumulative consumption Wh | Wh |
| 0x0120 | 1 | Charging state (low byte) + load_on (bit 15) | — |
| 0x0121 | 2 | Fault & warning bitfield (32-bit) | — |

### Charging state values (low byte of 0x0120)

| Value | State |
|---|---|
| 0 | Deactivated |
| 1 | Activated |
| 2 | MPPT |
| 3 | Equalizing |
| 4 | Boost |
| 5 | Floating |
| 6 | Current limit |

### Fault bitfield (0x0121:0x0122 as 32-bit)

| Bit | Fault |
|---|---|
| 30 | Charge MOS short |
| 29 | Anti-reverse MOS short |
| 28 | PV panel reverse polarity |
| 27 | PV panel working point overvoltage |
| 26 | PV input side overvoltage |
| 25 | PV input side short |
| 24 | PV input over-power |
| 23 | Ambient temperature high |
| 22 | Controller temperature high |
| 21 | Load over-power |
| 20 | Load short |
| 19 | Battery undervoltage |
| 18 | Battery overvoltage |
| 17 | Battery over-discharge |

## Polling cadences

See [ADR-0003](decisions/0003-poll-cadences.md). Briefly:

- **Real-time + state + faults**: every 30 s. ~2,880 rows/day, ~1 M/year.
- **Daily aggregates**: every 5 min as an upsert by `date`. The Wanderer
  resets these at controller-local midnight.
- **Lifetime counters**: every 1 h.

## Schema rationale

Four tables, each with a clear write cadence and grain:

- `telemetry` — append-only, `ts` PK, indexed `(ts DESC)`. Time-series shape.
- `daily` — upsert by `date`, contains the in-flight current day plus
  history.
- `lifetime` — append-only snapshots; lets us graph long-term trends and
  detect counter resets.
- `events` — append-only, only writes when `fault_word` changes. Sparse.

No TimescaleDB. At this poll rate, plain Postgres handles it for years.

## Service topology

Two systemd units:

- `helios.service` — the poll daemon
- `helios-web.service` — Flask via gunicorn

The web service has `After=helios.service` but starting helios-web doesn't
strictly require helios to be running — the dashboard will simply show
stale data if the daemon is down.

## Frontend

- Server-rendered Jinja with all data fetched client-side via JSON API.
- Chart.js 4 with the `chartjs-adapter-date-fns` time scale adapter.
- Refresh interval: 30 s, matching the daemon's real-time poll cadence.
- Monkey Theme — IBM Plex Mono + Bebas Neue, cyan/orange/green on
  near-black, cyan-tinted-alpha borders. See `web/static/css/monkey.css`
  which is a pinned copy of the canonical `.shared/monkey-theme.css`.
