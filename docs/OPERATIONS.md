# Operations

## Service control

```bash
# Status
systemctl status helios helios-web

# Restart (e.g. after config change)
systemctl restart helios

# Stop / start
systemctl stop helios helios-web
systemctl start helios helios-web

# Disable on boot
systemctl disable helios helios-web
```

## Logs

```bash
# Live tail
journalctl -u helios -f
journalctl -u helios-web -f

# Last N lines
journalctl -u helios -n 100 --no-pager

# Since timestamp
journalctl -u helios --since "1 hour ago"
journalctl -u helios --since "2026-06-04 12:00"

# Errors only
journalctl -u helios -p err
```

## Database

```bash
# Connect as superuser (peer auth via socket)
sudo -u postgres psql -d helios

# Or as helios with password
PGPASSWORD=$(grep HELIOS_DB_PASS /etc/helios/db.env | cut -d= -f2) \
  psql -h 127.0.0.1 -U helios -d helios

# Row counts across all tables
sudo -u postgres psql -d helios -c "
SELECT 'telemetry' AS tbl, count(*), max(ts) AS latest FROM telemetry
UNION ALL SELECT 'daily',    count(*), max(updated_at)::timestamptz FROM daily
UNION ALL SELECT 'lifetime', count(*), max(ts) FROM lifetime
UNION ALL SELECT 'events',   count(*), max(ts) FROM events;"

# Latest telemetry row
sudo -u postgres psql -d helios -c "SELECT * FROM telemetry ORDER BY ts DESC LIMIT 1;"

# Today's aggregates
sudo -u postgres psql -d helios -c "SELECT * FROM daily WHERE date = CURRENT_DATE;"

# Lifetime trend (daily peak)
sudo -u postgres psql -d helios -c "
SELECT date_trunc('day', ts) AS day, max(cumulative_gen_wh) AS gen_wh
FROM lifetime GROUP BY 1 ORDER BY 1 DESC LIMIT 10;"
```

## Manual probe

For debugging Modbus connectivity without involving the daemon:

```bash
/opt/helios/bin/python /opt/helios/probe.py
```

Or a one-liner for a single register:

```bash
/opt/helios/bin/python -c "
from pymodbus.client import ModbusTcpClient
from pymodbus import FramerType
c = ModbusTcpClient(host='10.200.200.201', port=4660, framer=FramerType.RTU, timeout=3)
c.connect()
r = c.read_holding_registers(address=0x0101, count=1, device_id=255)
print(f'Battery: {r.registers[0]/10.0} V')
"
```

## Backups

Nightly Postgres dump is recommended but not yet automated. Manual:

```bash
sudo -u postgres pg_dump -Fc helios > helios-$(date +%Y%m%d).pgcustom
```

Restore:

```bash
sudo -u postgres pg_restore -d helios helios-20260604.pgcustom
```

## Common issues

### Daemon shows "No response received"

The Modbus controller isn't replying. Check, in order:

1. **TCP path**: `nc -zv 10.200.200.201 4660` from the helios LXC.
2. **Gateway config**: VirtualCOM mode must be **off**, inter-character
   time gap ≥ 50 ms, serial set to 9600 / 8 / N / 1.
3. **Slave ID**: try `device_id=1` and `device_id=255` (Renogy broadcast).
4. **Cabling**: RJ12 pin 1 (TX) → DB9 pin 2 (RX), pin 2 → 3, pin 3 → 5.

### Web dashboard shows "CONNECTION ERROR"

The browser can't reach the API. Check `journalctl -u helios-web` —
most likely Flask/gunicorn crashed (try `sudo -u helios psql` to verify
Postgres connectivity).

### Time gap between rows > 30 s

Something is blocking the daemon. `top` and `journalctl -u helios -p err`.
Common causes: Postgres slow query, network blip, controller silent for
> 3 s timeout.

## Rotating the DB password

```bash
NEW=$(openssl rand -hex 16)
sudo -u postgres psql -c "ALTER USER helios WITH PASSWORD '$NEW';"
sudo sed -i "s/^HELIOS_DB_PASS=.*/HELIOS_DB_PASS=$NEW/" /etc/helios/db.env
sudo systemctl restart helios helios-web
```
