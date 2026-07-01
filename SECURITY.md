# Security

## Threat model

helios runs in a lab LXC. It listens on TCP/5000 (Flask) and connects
out to the configured Modbus gateway (TCP; currently either the EarthCam
EC-SS501 on port 4660 or the StarTech NETRS2321P on port 4001). It is
**not** designed to be exposed to the public internet. Postgres listens
on `127.0.0.1:5432` only.

Tailscale provides the access path to the dashboard. ACL policy gates
which devices can reach helios.

## Credentials

- `/etc/helios/db.env` — Postgres password. Mode 640, owner `root:helios`.
- `/etc/helios/admin.env` — bcrypt-hashed admin password + Flask secret
  key. Mode 640, owner `root:helios`.
- `/etc/helios/controller.env` — gateway IP, port, slave ID, poll
  cadences. Not sensitive, but mode **660 root:helios** so the web app
  (running as `helios`) can rewrite it via the /admin form. See
  ADR-0004 for the rationale.
- Real `.env` files **never** committed to the repo. Only `*.env.example`
  templates ship.

## Authentication

The dashboard requires login (v0.2.0+). Flask-Login session cookies,
bcrypt-hashed password (cost factor 12). Session lifetime 12 h. Cookies
are `HttpOnly` and `SameSite=Lax`, signed with a per-instance random
secret key.

There is no rate limiting on the login form. The trusted-network
assumption (Tailscale ACL) is the primary gate; auth is defense in
depth.

## Attack surface

| Component | Listening | Auth | Notes |
|---|---|---|---|
| Flask dashboard (gunicorn) | `0.0.0.0:5000` | Session cookie | Trusted network + Flask-Login |
| Postgres | `127.0.0.1:5432` | Password | Local only |
| Modbus client (outbound) | n/a | None | Talks to configured gateway |
| systemd path unit | inotify on `controller.env` | n/a | Triggers restart on file change |
| systemd journald | n/a | n/a | `journalctl -u helios -u helios-web -u helios-restart` |

## Privilege model

- Both `helios.service` (daemon) and `helios-web.service` (web app) run
  as the unprivileged `helios` user with `NoNewPrivileges=true`.
- The web app **cannot** escalate. It writes only to `/opt/helios/` and
  the single file `/etc/helios/controller.env`.
- Daemon restarts after a config change are driven by
  `helios-config.path` (a systemd path unit watching `controller.env`)
  triggering `helios-restart.service` (a one-shot that runs
  `systemctl restart helios.service`). Both run under systemd's own
  init privileges, never touching the web app's context.
- No sudoers grants. No `/var/lib/helios/` staging directory.

## Hardening (both helios and helios-web)

```
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
PrivateDevices=true
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true
RestrictAddressFamilies=AF_INET AF_INET6 AF_UNIX
LockPersonality=true
```

`helios.service` has `ReadWritePaths=/opt/helios` only.
`helios-web.service` has `ReadWritePaths=/opt/helios /etc/helios/controller.env`.

The `helios` service user has shell `/usr/sbin/nologin` and no home
directory.

## Reporting

Security issues that affect the helios codebase (not your deployment):
open a private security advisory on the GitHub repo, or contact the
SuperAngryMonkey maintainer directly.
