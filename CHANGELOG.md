# Changelog

All notable changes to helios are documented here.

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) ·
Versioning: [SemVer](https://semver.org/spec/v2.0.0.html)

## [Unreleased]

## [0.2.0] — 2026-06-05

### Added

- **Authentication** via Flask-Login. All routes (HTML and JSON API)
  require login. Single-user system; bcrypt-hashed password and Flask
  secret key stored in `/etc/helios/admin.env`.
- **Login page** at `/login` — Monkey-themed, centered card.
- **Admin page** at `/admin` — form to edit `CTRL_HOST`, `CTRL_PORT`,
  `CTRL_DEVICE_ID`, and the three poll cadences. Atomically rewrites
  `/etc/helios/controller.env` and restarts the helios daemon on save.
- **`passwd.py` CLI helper** — generates the bcrypt hash, writes
  `/etc/helios/admin.env`. Run as `sudo /opt/helios/bin/python /opt/helios/passwd.py`.
- **Sudoers grant** in `helios.sudoers` — narrow privileges for daemon
  restart and config install. No shell, no other privileges.
- **Nav links** on the dashboard header: Admin · Logout.
- **ADR-0004** documenting the auth + admin pattern.

### Changed

- `web/app.py` rewritten to add Flask-Login wiring, `@login_required`
  decorators on every route, and the admin form handler with input
  validation.
- `web/templates/index.html` gains Admin and Logout links in the header.
- `requirements.txt` adds `Flask-Login` and `bcrypt`.

### Security

- Session cookies: `HttpOnly`, `SameSite=Lax`, signed with
  `HELIOS_SECRET_KEY`.
- Session lifetime: 12 hours.
- Bcrypt cost factor: 12.
- Sudoers grant is two specific commands — no wildcard expansion that
  could be exploited.

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
