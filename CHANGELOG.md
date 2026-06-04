# Changelog

All notable changes to helios are documented here.

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) ·
Versioning: [SemVer](https://semver.org/spec/v2.0.0.html)

## [Unreleased]

## [0.1.0] — 2026-06-04

Initial public release.

### Added

- `helios.py` Modbus RTU poll daemon — 30 s real-time, 5 min daily, 1 h lifetime
- `web/app.py` Flask dashboard + JSON API (5 endpoints)
- `web/templates/index.html` Monkey-themed status page
- `web/static/js/charts.js` Chart.js 4 timeseries with 30 s auto-refresh
- `web/static/css/monkey.css` pinned canonical Monkey Theme
- `sql/schema.sql` four-table schema: telemetry / daily / lifetime / events
- `systemd/helios.service` and `helios-web.service` units with hardening
- `probe.py` standalone Modbus probe
- `config/*.env.example` configuration templates
- `docs/` design, operations, three ADRs

### Hardware tested

- Renogy Wanderer 30A (RNG-CTRL-WND30); 607 days operating, 6.2 kWh
  lifetime generation at first successful poll.
- EarthCam EC-SS501 serial gateway ("TerminalSrv v3.600MU"), TCP-server
  mode on port 4660.
