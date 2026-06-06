# 0004 — Authentication and admin UI

Date: 2026-06-05 · Status: Accepted

## Context

helios v0.1.0 served the dashboard with no authentication, relying on
Tailscale ACL to gate access. As the next phase, we want:

1. A login page so the dashboard isn't visible to anyone who happens onto
   the LAN/tailnet.
2. An admin page where the controller IP, port, slave ID, and poll
   cadences can be changed without SSH'ing into the LXC.

## Options considered

### Auth

1. **Flask-Login** with session cookies, single admin user.
2. **HTTP Basic Auth** via gunicorn or an nginx reverse proxy.
3. **OAuth/SSO via Tailscale identity** (Tailscale Funnel + serve config).
4. No auth, rely on ACL only (the v0.1.0 status quo).

### Admin file writes

1. **Sudoers grant** — `helios` user gets narrow `sudo install` and
   `sudo systemctl restart`.
2. **Loosen perms** — chmod 660 on `/etc/helios/controller.env`, chown
   helios:helios.
3. **Daemon listens for HUP** — web app writes config, signals daemon,
   daemon reloads. Requires daemon code changes and a config-watcher.
4. **Sidecar agent** — separate root-running service that the web app
   talks to over a Unix socket.

## Decisions

- **Flask-Login** for auth.
- **Sudoers grant** for the file write + daemon restart.

## Rationale

### Why Flask-Login

- Canonical Flask auth pattern; plays nicely with `@login_required`
  decorators across all routes.
- Session cookies are simpler than Basic Auth (no browser realm dialogs,
  clean logout, no external auth service required).
- Tailscale-identity-based auth (option 3) is interesting but adds setup
  complexity and couples auth to one network layer. Plain session auth
  works regardless of how the user reaches the LXC.

### Why sudoers (not loosened perms)

- **Auditable**: every config change leaves a `sudo` log entry.
- **Narrow**: the grant is exactly two specific commands with fixed
  paths and no wildcards — no shell escape.
- **Reversible**: revoking the sudoers grant disables admin writes
  immediately, without touching file ownership.
- The alternative (chmod 660) gives the helios user permanent write
  access to its own config — slightly broader attack surface if the
  web app is compromised.

### Single-user system

We're not building a multi-tenant SaaS. One admin per helios instance
matches the deployment reality. Skipping a `users` table keeps the
schema clean and lets credentials live in env files (the existing pattern).

## Implementation notes

- New file `/etc/helios/admin.env` (mode 640, root:helios) with three keys:
  `HELIOS_ADMIN_USER`, `HELIOS_ADMIN_PASS_HASH`, `HELIOS_SECRET_KEY`.
- New file `/etc/sudoers.d/helios` — see `helios.sudoers` in the repo.
- New directory `/var/lib/helios/` (mode 700, helios:helios) — staging
  path for atomic config writes.
- `passwd.py` is a setup tool; it bypasses the sudo flow because it runs
  as root directly from an SSH session.

## Consequences

- New dependencies: `Flask-Login`, `bcrypt`.
- All API endpoints become authenticated. External callers (a future
  Grafana data source, a future Heimdall consumer, etc.) would need to
  either share a session cookie or use an API token mechanism that
  doesn't yet exist. ADR-0005 reserved for the API token pattern when
  the first external consumer arrives.
- Daemon restart on save means a ~3–5 second blackout where the
  dashboard shows stale data and the daemon misses one poll cycle.
  Acceptable for a tool that polls every 30 s.
