# helios — handoff

Current state as of 2026-06-04.

## What's working

- **Daemon** (`helios.service`) polling every 30 s and writing to Postgres.
  Verified telemetry rows landing at correct cadence; daily, lifetime, and
  events tables all populating.
- **Web** (`helios-web.service`) on port 5000 via gunicorn (2 workers).
  Monkey-themed dashboard renders 4 metric tiles, 2 timeseries, an
  aggregate `.fg` strip, and the *POST TENEBRAS LUX* epigraph.
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
- [ ] **Grafana 13 provisioning bug**: legacy YAML failed silently with
      misleading "data source not found". Move-aside-and-add-via-UI worked
      around it. If revisited, try disabling the `provisioning` feature flag.
- [ ] **Dev-mode hook in `web/app.py`**: the `if __name__ == '__main__'`
      block calls `app.run(host="0.0.0.0", port=5000, debug=True)`. Used
      during smoke test; gunicorn ignores it in production but leaving it
      in is a footgun if anyone runs `python app.py` directly. Consider
      removing.
- [ ] **First-cycle fault event**: every daemon restart inserts a
      "fault cleared" event row because `last_fault` starts at `-1`. Could
      skip the initial insert when transitioning `-1 → 0`.

## Watch list

- **Wanderer Modbus stability**: if reads stop returning, probe with
  `device_id=1` and `device_id=255` to confirm slave address.
- **Gateway buffer flushing**: inter-character time gap is set to 50 ms.
  If Modbus frames start fragmenting, raise to 100 ms in the gateway UI.
- **Time drift**: LXC clock is critical for the `daily` table primary key.
  Confirm `timedatectl` reports NTP-synchronized.

## Next features (priority order)

1. **`/faults` page** — table of recent fault events, decoded bitfield names.
2. **`/history` page** — 30-day trend of generated vs consumed Wh, daily
   battery V min/max sparkline.
3. **Alerting** — simple threshold checker (`battery_v < 11.5`, fault
   word non-zero) firing a webhook (Slack, iMessage relay).
4. **Multi-controller support** — when the airboat install or a Lauderdale
   solar setup is wired, helios becomes a multi-tenant collector. Add
   `controller_id` to schema, support multiple
   `/etc/helios/controllers/*.env` files.

## Provenance

Built 2026-06-04 in a single Cyrano session. Bootstrap from nothing to
working dashboard in ~3 hours, including a Grafana detour we backed out of.
