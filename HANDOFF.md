# helios — handoff

Current state as of 2026-06-05 (v0.2.0).

## What's working

- **Daemon** (`helios.service`) polling every 30 s and writing to Postgres.
- **Web** (`helios-web.service`) on port 5000 via gunicorn (2 workers),
  Monkey-themed dashboard with 4 metric tiles, 2 timeseries, aggregate strip.
- **Authentication** (v0.2.0): Flask-Login session auth, single admin user,
  bcrypt hash in `/etc/helios/admin.env`. All routes (HTML + JSON API)
  require login. Login page at `/login`, logout at `/logout`.
- **Admin page** (v0.2.0): `/admin` form for editing controller IP, port,
  device ID, and poll cadences. Saves atomically rewrite
  `/etc/helios/controller.env` and restart the daemon via a narrow sudoers
  grant.
- **Postgres** local on the LXC, schema applied, indices on `(ts DESC)`.
- **Gateway**: EarthCam EC-SS501 ("TerminalSrv v3.600MU" firmware) at
  10.200.200.201:4660 in TCP-server mode. Slave 255 (Renogy broadcast).
- **Tailscale**: enrolled as `helios.bobcat-gondola.ts.net` (100.127.229.72).

## Lab deployment

- **Proxmox host**: proxlab (10.0.1.9 / TS 100.105.71.57)
- **LXC**: helios — 10.0.1.149 / TS 100.127.229.72
- **Subnets in scope**: 10.0.1.0/24 (lab), 10.200.200.0/24 (controller VLAN)
- **Resources**: 1 vCPU / 1 GB RAM / 8 GB disk, Debian 12

## Open items

- [ ] **Tailscale tag**: the helios LXC is untagged. Other lab boxes
      (agora, apc-dev, etc.) are `tag:tagged-devices`. Run
      `tailscale up --advertise-tags=tag:tagged-devices --reset` and
      approve in the admin console.
- [ ] **Grafana**: installed but disabled — left in place for potential
      reuse on Heimdall. To fully uninstall:
      `apt purge grafana && rm -rf /etc/grafana /var/lib/grafana`.
- [ ] **Dev-mode hook in `web/app.py`**: the `if __name__ == '__main__'`
      block calls `app.run(debug=True)`. Gunicorn ignores it; harmless but
      a footgun if anyone runs `python app.py` directly.
- [ ] **First-cycle "fault cleared" event** on daemon restart: cosmetic
      but writes a noisy `events` row on every restart because
      `last_fault` starts at `-1`.
- [ ] **Threshold-based color on metric tiles**: SOC and Battery V tiles
      are hard-coded `green` in the template. Should turn orange/red
      based on the value. JS-side class toggling.
- [ ] **Bigger PV panel install** (hardware): rewire load + serial
      adapter after panel swap. Watch charge current ≤ 0.3C of AGM bank.

## Watch list

- **Wanderer Modbus stability**: if reads stop, probe with `device_id=1`
  and `device_id=255` to confirm slave address.
- **Gateway buffer flushing**: inter-character time gap is set to 50 ms.
  If Modbus frames start fragmenting, raise to 100 ms in the gateway UI.
- **Time drift**: LXC clock is critical for `daily` table key. Confirm
  `timedatectl` reports NTP-synchronized.
- **`/var/lib/helios/controller.env.new`**: present briefly during admin
  saves, then `install`'d into place. Should never persist between saves.

## Next features (priority order)

1. **`/faults` page** — table of recent fault events, decoded bitfield
   names from the `events` table.
2. **`/history` page** — 30-day trend of generated vs consumed Wh, daily
   battery V min/max sparkline.
3. **Threshold-based colors** — see Open items above.
4. **Alerting** — simple threshold checker (`battery_v < 11.5`, fault
   word non-zero) firing a webhook (Slack, iMessage relay).
5. **API token mechanism** — for external consumers to hit the JSON API
   without sharing a session cookie. ADR-0005 reserved.
6. **Multi-controller support** — when the airboat install or a
   Lauderdale solar setup is wired. Add `controller_id` to schema,
   support multiple `/etc/helios/controllers/*.env` files.

## Provenance

- v0.1.0 (2026-06-04): bootstrap from nothing to working dashboard,
  ~3 hours including a Grafana detour we backed out of.
- v0.2.0 (2026-06-05): authentication + admin page, ~45 minutes.
