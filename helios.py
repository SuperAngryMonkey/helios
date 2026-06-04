#!/opt/helios/bin/python
"""
helios — Renogy Wanderer 30A telemetry daemon
Polls Modbus RTU over Ethernet serial server, writes to Postgres.
"""
import os, sys, time, signal, logging
from datetime import date
from pathlib import Path

import psycopg2
from pymodbus.client import ModbusTcpClient
from pymodbus import FramerType


# --- Config ---
def load_env(path):
    env = {}
    for line in Path(path).read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env

DB_ENV = load_env("/etc/helios/db.env")
CTRL = load_env("/etc/helios/controller.env")
REALTIME_SEC = int(CTRL.get("HELIOS_REALTIME_SEC", "30"))
DAILY_SEC    = int(CTRL.get("HELIOS_DAILY_SEC",    "300"))
LIFETIME_SEC = int(CTRL.get("HELIOS_LIFETIME_SEC", "3600"))


# --- Logging (stdout → journald) ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
    stream=sys.stdout,
)
log = logging.getLogger("helios")


# --- Register decoding ---
CHARGE_STATES = {
    0: "deactivated", 1: "activated", 2: "mppt", 3: "equalizing",
    4: "boost", 5: "floating", 6: "current_limit",
}

FAULT_BITS = [
    (30, "charge_mos_short"),
    (29, "anti_reverse_mos_short"),
    (28, "pv_panel_reverse"),
    (27, "pv_working_point_over"),
    (26, "pv_input_overvoltage"),
    (25, "pv_input_short"),
    (24, "pv_input_overpower"),
    (23, "ambient_temp_high"),
    (22, "controller_temp_high"),
    (21, "load_overpower"),
    (20, "load_short"),
    (19, "battery_undervoltage"),
    (18, "battery_overvoltage"),
    (17, "battery_overdischarge"),
]

def fault_description(word):
    if word == 0:
        return None
    active = [name for bit, name in FAULT_BITS if word & (1 << bit)]
    return ",".join(active) if active else f"unknown_0x{word:08x}"

def signed_byte(v):
    return v - 256 if v >= 128 else v


# --- Modbus client ---
class Wanderer:
    def __init__(self, host, port, dev_id, timeout=3):
        self.host, self.port, self.dev_id, self.timeout = host, int(port), int(dev_id), timeout
        self.c = None

    def connect(self):
        self.c = ModbusTcpClient(host=self.host, port=self.port,
                                 framer=FramerType.RTU, timeout=self.timeout)
        return self.c.connect()

    def close(self):
        if self.c:
            try: self.c.close()
            except Exception: pass

    def _read(self, addr, count):
        r = self.c.read_holding_registers(address=addr, count=count, device_id=self.dev_id)
        if r.isError():
            raise RuntimeError(f"modbus err @0x{addr:04x}+{count}: {r}")
        return r.registers

    def realtime(self):
        regs = self._read(0x0100, 10)
        soc, batt_v, charge_i, temp_w, lv, li, lp, pv_v, pv_i, pv_p = regs
        state_word = self._read(0x0120, 1)[0]
        return {
            "battery_soc": soc,
            "battery_v": batt_v / 10.0,
            "charge_i":  charge_i / 100.0,
            "battery_temp_c":    signed_byte(temp_w & 0xFF),
            "controller_temp_c": signed_byte(temp_w >> 8),
            "load_v": lv / 10.0,
            "load_i": li / 100.0,
            "load_w": lp,
            "pv_v":   pv_v / 10.0,
            "pv_i":   pv_i / 100.0,
            "pv_w":   pv_p,
            "charge_state": state_word & 0xFF,
            "load_on": bool(state_word & 0x8000),
        }

    def daily(self):
        vmin, vmax, imc, imd, pmc, pmd, ahc, ahd, whg, whu = self._read(0x010B, 10)
        return {
            "batt_v_min": vmin / 10.0, "batt_v_max": vmax / 10.0,
            "charge_i_max": imc / 100.0, "discharge_i_max": imd / 100.0,
            "charge_w_max": pmc, "discharge_w_max": pmd,
            "charge_ah": ahc, "discharge_ah": ahd,
            "generated_wh": whg, "consumed_wh": whu,
        }

    def lifetime(self):
        r = self._read(0x0115, 11)
        return {
            "operating_days":   r[0],
            "over_discharges":  r[1],
            "full_charges":     r[2],
            "cumulative_charge_ah":    (r[3] << 16) | r[4],
            "cumulative_discharge_ah": (r[5] << 16) | r[6],
            "cumulative_gen_wh":       (r[7] << 16) | r[8],
            "cumulative_cons_wh":      (r[9] << 16) | r[10],
        }

    def faults(self):
        hi, lo = self._read(0x0121, 2)
        return (hi << 16) | lo


# --- DB ---
class DB:
    def __init__(self, env): self.env = env; self.conn = None
    def connect(self):
        self.conn = psycopg2.connect(
            host=self.env["HELIOS_DB_HOST"], port=self.env["HELIOS_DB_PORT"],
            dbname=self.env["HELIOS_DB_NAME"], user=self.env["HELIOS_DB_USER"],
            password=self.env["HELIOS_DB_PASS"],
        )
        self.conn.autocommit = True

    def ensure(self):
        if self.conn is None or self.conn.closed:
            self.connect()
        else:
            try:
                with self.conn.cursor() as cur: cur.execute("SELECT 1")
            except psycopg2.Error:
                self.connect()

    def write_telemetry(self, d):
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO telemetry (battery_soc, battery_v, charge_i,
                  battery_temp_c, controller_temp_c, load_v, load_i, load_w,
                  pv_v, pv_i, pv_w, charge_state, load_on)
                VALUES (%(battery_soc)s, %(battery_v)s, %(charge_i)s,
                        %(battery_temp_c)s, %(controller_temp_c)s, %(load_v)s,
                        %(load_i)s, %(load_w)s, %(pv_v)s, %(pv_i)s, %(pv_w)s,
                        %(charge_state)s, %(load_on)s)
            """, d)

    def upsert_daily(self, d):
        d = dict(d); d["date"] = date.today()
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO daily (date, batt_v_min, batt_v_max, charge_i_max,
                  discharge_i_max, charge_w_max, discharge_w_max, charge_ah,
                  discharge_ah, generated_wh, consumed_wh, updated_at)
                VALUES (%(date)s, %(batt_v_min)s, %(batt_v_max)s, %(charge_i_max)s,
                        %(discharge_i_max)s, %(charge_w_max)s, %(discharge_w_max)s,
                        %(charge_ah)s, %(discharge_ah)s, %(generated_wh)s,
                        %(consumed_wh)s, now())
                ON CONFLICT (date) DO UPDATE SET
                  batt_v_min = EXCLUDED.batt_v_min, batt_v_max = EXCLUDED.batt_v_max,
                  charge_i_max = EXCLUDED.charge_i_max, discharge_i_max = EXCLUDED.discharge_i_max,
                  charge_w_max = EXCLUDED.charge_w_max, discharge_w_max = EXCLUDED.discharge_w_max,
                  charge_ah = EXCLUDED.charge_ah, discharge_ah = EXCLUDED.discharge_ah,
                  generated_wh = EXCLUDED.generated_wh, consumed_wh = EXCLUDED.consumed_wh,
                  updated_at = now()
            """, d)

    def write_lifetime(self, d):
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO lifetime (operating_days, over_discharges, full_charges,
                  cumulative_charge_ah, cumulative_discharge_ah,
                  cumulative_gen_wh, cumulative_cons_wh)
                VALUES (%(operating_days)s, %(over_discharges)s, %(full_charges)s,
                        %(cumulative_charge_ah)s, %(cumulative_discharge_ah)s,
                        %(cumulative_gen_wh)s, %(cumulative_cons_wh)s)
            """, d)

    def write_event(self, fault_word, desc):
        with self.conn.cursor() as cur:
            cur.execute("INSERT INTO events (fault_word, description) VALUES (%s, %s)",
                        (fault_word, desc))


# --- Main loop ---
def main():
    log.info("helios start")
    log.info(f"controller {CTRL['CTRL_HOST']}:{CTRL['CTRL_PORT']} dev={CTRL['CTRL_DEVICE_ID']}")
    log.info(f"intervals: rt={REALTIME_SEC}s daily={DAILY_SEC}s lifetime={LIFETIME_SEC}s")

    db = DB(DB_ENV); db.connect()
    log.info("postgres connected")

    w = Wanderer(CTRL["CTRL_HOST"], CTRL["CTRL_PORT"], CTRL["CTRL_DEVICE_ID"])
    w.connect()
    log.info("controller connected")

    last_daily = 0.0
    last_lifetime = 0.0
    last_fault = -1

    stop = {"now": False}
    def _stop(sig, frame):
        log.info(f"signal {sig}; shutting down")
        stop["now"] = True
    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT,  _stop)

    while not stop["now"]:
        t0 = time.time()
        try:
            db.ensure()

            rt = w.realtime()
            db.write_telemetry(rt)
            log.info(
                f"rt soc={rt['battery_soc']}% v={rt['battery_v']:.1f} "
                f"pv={rt['pv_w']}W load={rt['load_w']}W "
                f"state={CHARGE_STATES.get(rt['charge_state'], '?')}"
            )

            fw = w.faults()
            if fw != last_fault:
                desc = fault_description(fw)
                db.write_event(fw, desc)
                (log.info("fault cleared") if fw == 0 else log.warning(f"fault 0x{fw:08x} ({desc})"))
                last_fault = fw

            if t0 - last_daily >= DAILY_SEC:
                d = w.daily(); db.upsert_daily(d); last_daily = t0
                log.info(f"daily gen={d['generated_wh']}Wh used={d['consumed_wh']}Wh")

            if t0 - last_lifetime >= LIFETIME_SEC:
                lt = w.lifetime(); db.write_lifetime(lt); last_lifetime = t0
                log.info(f"lifetime days={lt['operating_days']} gen={lt['cumulative_gen_wh']}Wh")

        except Exception as e:
            log.error(f"cycle failed: {e}")
            w.close(); time.sleep(5)
            try: w.connect()
            except Exception as ce: log.error(f"reconnect failed: {ce}")

        elapsed = time.time() - t0
        time.sleep(max(0.0, REALTIME_SEC - elapsed))

    w.close()
    try: db.conn.close()
    except Exception: pass
    log.info("helios stopped")


if __name__ == "__main__":
    main()
