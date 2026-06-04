# helios

> *Post tenebras lux.*
> — Geneva motto, after the Vulgate (Job 17:12)

Telemetry daemon and Monkey-themed dashboard for the Renogy Wanderer 30A
solar charge controller. Modbus RTU over an Ethernet-to-serial gateway,
Postgres for persistence, Flask for a live status page. No phone app, no
cloud, no BT-1 dongle — just bytes on the wire and a browser tab.

## What it does

- Polls the Wanderer every 30 seconds for SOC, battery V, PV/load power,
  charging state, controller temperature, and the fault bitfield.
- Aggregates daily counters (Wh generated/consumed, V min/max, peak A/W)
  every 5 minutes.
- Snapshots lifetime counters (operating days, cumulative kWh) every hour.
- Writes everything to a local Postgres instance.
- Serves a Monkey-themed Flask dashboard at `http://helios:5000/` with
  24h Chart.js timeseries and live numbers refreshing every 30 s.

## Architecture

```
┌──────────────────────┐
│ Renogy Wanderer 30A  │
└──────────┬───────────┘
           │ Modbus RTU over RS232 (RJ12)
           │ 9600 8N1, slave 255
           ▼
┌──────────────────────┐
│ Serial→Ethernet GW   │ TCP server, port 4660
└──────────┬───────────┘
           │ Modbus RTU framed over raw TCP
           ▼
┌──────────────────────┐
│ helios LXC           │
│ ├─ helios.py         │ pymodbus + psycopg2 daemon
│ ├─ web/app.py        │ Flask + gunicorn on :5000
│ └─ Postgres 15       │ telemetry · daily · lifetime · events
└──────────────────────┘
           │
           ▼
  http://helios.bobcat-gondola.ts.net:5000
```

## Stack

- Debian 12 LXC on Proxmox
- Python 3.11 (`pymodbus` 3.13, `psycopg2-binary`, `Flask` 3.1, `gunicorn`)
- PostgreSQL 15
- Chart.js 4 + `chartjs-adapter-date-fns`
- Monkey Theme — IBM Plex Mono + Bebas Neue, cyan/orange/green on near-black

## Quickstart

Prerequisites: a Linux box (LXC, VM, bare metal) that can reach your
serial-to-Ethernet gateway over the network.

```bash
# 1. Install deps
apt install -y python3-venv python3-pip postgresql postgresql-contrib

# 2. Clone
git clone https://github.com/SuperAngryMonkey/helios /opt/helios-src
cd /opt/helios-src

# 3. Venv + Python deps
python3 -m venv /opt/helios
/opt/helios/bin/pip install -r requirements.txt

# 4. Postgres
sudo -u postgres psql -c "CREATE USER helios WITH PASSWORD 'CHANGEME';"
sudo -u postgres psql -c "CREATE DATABASE helios OWNER helios;"
sudo -u postgres psql -d helios -f sql/schema.sql

# 5. Config
sudo mkdir -p /etc/helios && sudo chmod 750 /etc/helios
sudo cp config/db.env.example         /etc/helios/db.env
sudo cp config/controller.env.example /etc/helios/controller.env
sudo $EDITOR /etc/helios/db.env /etc/helios/controller.env

# 6. Service user
sudo useradd --system --shell /usr/sbin/nologin --no-create-home helios
sudo chown root:helios /etc/helios /etc/helios/*.env
sudo chmod 750 /etc/helios && sudo chmod 640 /etc/helios/*.env

# 7. Drop code under the venv prefix
sudo cp helios.py probe.py /opt/helios/
sudo cp -r web /opt/helios/
sudo chown -R helios:helios /opt/helios/helios.py /opt/helios/probe.py /opt/helios/web

# 8. systemd
sudo cp systemd/helios*.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now helios helios-web

# 9. Confirm
sudo systemctl status helios helios-web
xdg-open http://localhost:5000
```

## Files

| Path | Purpose |
|---|---|
| `helios.py` | Main poll daemon |
| `probe.py` | Standalone ad-hoc Modbus read |
| `web/app.py` | Flask web app (Postgres → JSON API + HTML) |
| `web/templates/` | Jinja templates (base, index) |
| `web/static/css/monkey.css` | Pinned copy of canonical Monkey Theme |
| `web/static/js/charts.js` | Chart.js setup + 30s refresh loop |
| `sql/schema.sql` | Postgres DDL |
| `config/*.env.example` | Templates for `/etc/helios/*.env` |
| `systemd/*.service` | Unit files for the daemon + web app |

## Documentation

- [docs/DESIGN.md](docs/DESIGN.md) — register map, decoders, schema rationale
- [docs/OPERATIONS.md](docs/OPERATIONS.md) — systemd, logs, backups, common ops
- [docs/decisions/](docs/decisions/) — ADRs
- [HANDOFF.md](HANDOFF.md) — current deployment state, open items
- [CHANGELOG.md](CHANGELOG.md) — version history
- [SECURITY.md](SECURITY.md) — credentials handling, attack surface

## Hardware tested

- **Controller**: Renogy Wanderer 30A (RNG-CTRL-WND30)
- **Gateway**: EarthCam EC-SS501 (a rebadged Taiwanese "TerminalSrv v3.600MU"
  serial server). StarTech NETRS2321P and any TCP-server-mode serial gateway
  should also work.

## License

MIT — see [LICENSE](LICENSE).
