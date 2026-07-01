"""
helios.web — Monkey-themed dashboard for the Renogy Wanderer telemetry.
Reads from the same Postgres tables the helios daemon writes to.
Auth via Flask-Login. Admin page writes controller.env directly; a
systemd path unit watches the file and restarts the daemon on change.
"""
import os
import re
from pathlib import Path

import bcrypt
from flask import Flask, render_template, jsonify, request, redirect, url_for
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
import psycopg2
from psycopg2.extras import RealDictCursor


# --- Config loading ---
def load_env(path):
    env = {}
    for line in Path(path).read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env


DB    = load_env("/etc/helios/db.env")
CTRL  = load_env("/etc/helios/controller.env")
ADMIN = load_env("/etc/helios/admin.env")

CONTROLLER_ENV_PATH = "/etc/helios/controller.env"

CHARGE_STATES = {
    0: "deactivated", 1: "activated", 2: "mppt", 3: "equalizing",
    4: "boost", 5: "floating", 6: "current_limit",
}


# --- Flask + Login setup ---
app = Flask(__name__)
app.config["SECRET_KEY"] = ADMIN.get("HELIOS_SECRET_KEY", "insecure-default-rotate-me")
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["PERMANENT_SESSION_LIFETIME"] = 43200  # 12h

login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "Authentication required."


class AdminUser(UserMixin):
    def __init__(self, username):
        self.id = username
        self.username = username


@login_manager.user_loader
def load_user(user_id):
    if user_id and user_id == ADMIN.get("HELIOS_ADMIN_USER"):
        return AdminUser(user_id)
    return None


# --- DB helper ---
def get_conn():
    return psycopg2.connect(
        host=DB["HELIOS_DB_HOST"], port=DB["HELIOS_DB_PORT"],
        dbname=DB["HELIOS_DB_NAME"], user=DB["HELIOS_DB_USER"],
        password=DB["HELIOS_DB_PASS"],
        cursor_factory=RealDictCursor,
    )


def _float(v):
    return float(v) if v is not None else None


# --- Auth routes ---
@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("index"))

    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        expected_user = ADMIN.get("HELIOS_ADMIN_USER", "")
        expected_hash = ADMIN.get("HELIOS_ADMIN_PASS_HASH", "")
        ok = False
        if username and password and username == expected_user and expected_hash:
            try:
                ok = bcrypt.checkpw(password.encode(), expected_hash.encode())
            except (ValueError, TypeError):
                ok = False
        if ok:
            login_user(AdminUser(username), remember=False)
            next_url = request.args.get("next") or url_for("index")
            return redirect(next_url)
        error = "Invalid credentials."

    return render_template("login.html", error=error)


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))


# --- Main dashboard ---
@app.route("/")
@login_required
def index():
    return render_template("index.html")


# --- JSON API (all require auth) ---
@app.route("/api/realtime")
@login_required
def api_realtime():
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM telemetry ORDER BY ts DESC LIMIT 1")
        row = cur.fetchone()
        if row:
            row["ts"] = row["ts"].isoformat()
            row["charge_state_label"] = CHARGE_STATES.get(row["charge_state"], "unknown")
            for k in ("battery_v", "charge_i", "load_v", "load_i", "pv_v", "pv_i"):
                row[k] = _float(row[k])
        return jsonify(row)


@app.route("/api/timeseries")
@login_required
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
@login_required
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
            for k in ("batt_v_min", "batt_v_max", "charge_i_max", "discharge_i_max"):
                r[k] = _float(r[k])
            if r.get("updated_at"):
                r["updated_at"] = r["updated_at"].isoformat()
        return jsonify(rows)


@app.route("/api/lifetime")
@login_required
def api_lifetime():
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM lifetime ORDER BY ts DESC LIMIT 1")
        row = cur.fetchone()
        if row:
            row["ts"] = row["ts"].isoformat()
        return jsonify(row)


@app.route("/api/events")
@login_required
def api_events():
    limit = int(request.args.get("limit", 20))
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM events ORDER BY ts DESC LIMIT %s", (limit,))
        rows = cur.fetchall()
        for r in rows:
            r["ts"] = r["ts"].isoformat()
        return jsonify(rows)


# --- Admin page ---
ADMIN_FIELDS = [
    ("CTRL_HOST",           "Serial gateway IP / host",     r"^[a-zA-Z0-9._-]{1,253}$"),
    ("CTRL_PORT",           "Gateway TCP port",             r"^\d{1,5}$"),
    ("CTRL_DEVICE_ID",      "Modbus device ID (0–255)",     r"^\d{1,3}$"),
    ("HELIOS_REALTIME_SEC", "Real-time poll interval (s)",  r"^\d{1,5}$"),
    ("HELIOS_DAILY_SEC",    "Daily poll interval (s)",      r"^\d{1,6}$"),
    ("HELIOS_LIFETIME_SEC", "Lifetime poll interval (s)",   r"^\d{1,6}$"),
]


def _rewrite_env(values):
    """Preserve comments and ordering; substitute known keys; append new ones."""
    existing = Path(CONTROLLER_ENV_PATH).read_text().splitlines()
    out, seen = [], set()
    for line in existing:
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            out.append(line)
            continue
        key = s.split("=", 1)[0].strip()
        if key in values:
            out.append(f"{key}={values[key]}")
            seen.add(key)
        else:
            out.append(line)
    for k, v in values.items():
        if k not in seen:
            out.append(f"{k}={v}")
    return "\n".join(out) + "\n"


def _save_config(values):
    """
    Write controller.env directly. The helios-config.path systemd unit
    watches this file with inotify and triggers helios-restart.service
    on any modification, which restarts the daemon within ~1s.

    Requires controller.env to be group-writable by 'helios' (mode 660,
    root:helios). No sudo, no privilege escalation.
    """
    content = _rewrite_env(values)
    Path(CONTROLLER_ENV_PATH).write_text(content)


@app.route("/admin", methods=["GET", "POST"])
@login_required
def admin():
    error, success = None, None

    if request.method == "POST":
        try:
            new_values = {}
            for key, label, pattern in ADMIN_FIELDS:
                val = request.form.get(key, "").strip()
                if not val:
                    error = f"{label} is required."
                    break
                if not re.match(pattern, val):
                    error = f"{label} failed validation."
                    break
                new_values[key] = val
            if not error:
                _save_config(new_values)
                success = "Saved. Daemon will restart within a second."
                # Refresh in-process CTRL too
                global CTRL
                CTRL = load_env(CONTROLLER_ENV_PATH)
        except Exception as e:
            error = f"Save failed: {e}"

    current = load_env(CONTROLLER_ENV_PATH)
    return render_template("admin.html", fields=ADMIN_FIELDS, values=current,
                           error=error, success=success)


if __name__ == "__main__":
    # Dev only — production runs via gunicorn
    app.run(host="0.0.0.0", port=5000, debug=True)
