# Security

## Threat model

helios runs in a lab LXC. It listens on TCP/5000 (Flask) and connects out
to TCP/4660 (Modbus gateway). It is **not** designed to be exposed to the
public internet. Postgres listens on `127.0.0.1:5432` only.

Tailscale provides the access path to the dashboard. ACL policy gates
which devices can reach helios.

## Credentials

- `/etc/helios/db.env` — Postgres password. Mode 640, owner `root:helios`.
- `/etc/helios/controller.env` — gateway IP, port, slave ID. Not sensitive,
  but mode 640 to match.
- Real `.env` files **never** committed to the repo. Only `*.env.example`
  templates ship.

## Authentication

helios has **no authentication** on the web dashboard. It assumes the
network layer (Tailscale ACL, lab firewall) gates access. Do **not**
expose the LXC to the internet without an auth proxy in front.

## Attack surface

| Component | Listening | Auth | Notes |
|---|---|---|---|
| Flask dashboard (gunicorn) | `0.0.0.0:5000` | None | Trusted network only |
| Postgres | `127.0.0.1:5432` | Password | Local only |
| Modbus client (outbound) | n/a | None | Talks to gateway on TCP/4660 |
| systemd journald | n/a | n/a | `journalctl -u helios` |

## Hardening

The systemd units apply standard sandboxing:

```
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/opt/helios
PrivateDevices=true
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true
RestrictAddressFamilies=AF_INET AF_INET6 AF_UNIX
LockPersonality=true
```

The `helios` service user has shell `/usr/sbin/nologin` and no home
directory.

## Reporting

Security issues that affect the helios codebase (not your deployment):
open a private security advisory on the GitHub repo, or contact the
SuperAngryMonkey maintainer directly.
