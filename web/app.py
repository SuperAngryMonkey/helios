"""
helios.web — Monkey-themed dashboard for the Renogy Wanderer telemetry.
Reads from the same Postgres tables the helios daemon writes to.
"""
from flask import Flask, render_template, jsonify, request
import psycopg2
from psycopg2.extras import RealDictCursor
from pathlib import Path

def load_env(path):
    env = {}
    for line in Path(path).read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env

DB = load_env("/etc/helios/db.env")

app = Flask(__name__)

CHARGE_STATES = {
    0: "deactivated", 1: "activated", 2: "mppt", 3: "equalizing",
    4: "boost", 5: "floating", 6: "current_limit",
}

def get_conn():
    return psycopg2.connect(
        host=DB["HELIOS_DB_HOST"], port=DB["HELIOS_DB_PORT"],
        dbname=DB["HELIOS_DB_NAME"], user=DB["HELIOS_DB_USER"],
        password=DB["HELIOS_DB_PASS"],
        cursor_factory=RealDictCursor,
    )

def _float(v): return float(v) if v is not None else None

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/realtime")
def api_realtime():
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM telemetry ORDER BY ts DESC LIMIT 1")
        row = cur.fetchone()
        if row:
            row["ts"] = row["ts"].isoformat()
            row["charge_state_label"] = CHARGE_STATES.get(row["charge_state"], "unknown")
            for k in ("battery_v","charge_i","load_v","load_i","pv_v","pv_i"):
                row[k] = _float(row[k])
        return jsonify(row)

@app.route("/api/timeseries")
def api_timeseries():
    hours = int(request.args.get("hours", 24))
    bucket = max(30, hours * 3600 // 288)
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT
                to_timestamp(floor(extract(epoch FROM ts) / %s) * %s) AS bucket,
                avg(pv_w)::int AS pv_w,
                avg(load_w)::int AS load_w,
                avg(battery_v)::numeric(4,2) AS battery_v,
                avg(battery_soc)::int AS battery_soc
            FROM telemetry
            WHERE ts > now() - (%s || ' hours')::interval
            GROUP BY bucket
            ORDER BY bucket
        """, (bucket, bucket, hours))
        rows = cur.fetchall()
        for r in rows:
            r["bucket"] = r["bucket"].isoformat()
            r["battery_v"] = _float(r["battery_v"])
        return jsonify(rows)

@app.route("/api/daily")
def api_daily():
    days = int(request.args.get("days", 7))
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT * FROM daily
            WHERE date >= CURRENT_DATE - (%s || ' days')::interval
            ORDER BY date DESC
        """, (days,))
        rows = cur.fetchall()
        for r in rows:
            r["date"] = r["date"].isoformat()
            for k in ("batt_v_min","batt_v_max","charge_i_max","discharge_i_max"):
                r[k] = _float(r[k])
            if r.get("updated_at"):
                r["updated_at"] = r["updated_at"].isoformat()
        return jsonify(rows)

@app.route("/api/lifetime")
def api_lifetime():
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM lifetime ORDER BY ts DESC LIMIT 1")
        row = cur.fetchone()
        if row:
            row["ts"] = row["ts"].isoformat()
        return jsonify(row)

@app.route("/api/events")
def api_events():
    limit = int(request.args.get("limit", 20))
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM events ORDER BY ts DESC LIMIT %s", (limit,))
        rows = cur.fetchall()
        for r in rows:
            r["ts"] = r["ts"].isoformat()
        return jsonify(rows)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
