-- helios schema — Renogy Wanderer telemetry
-- Apply: psql -d helios -f schema.sql

CREATE TABLE IF NOT EXISTS telemetry (
    ts TIMESTAMPTZ PRIMARY KEY DEFAULT now(),
    battery_soc        SMALLINT,
    battery_v          NUMERIC(4,1),
    charge_i           NUMERIC(5,2),
    battery_temp_c     SMALLINT,
    controller_temp_c  SMALLINT,
    load_v             NUMERIC(4,1),
    load_i             NUMERIC(5,2),
    load_w             INTEGER,
    pv_v               NUMERIC(4,1),
    pv_i               NUMERIC(5,2),
    pv_w               INTEGER,
    charge_state       SMALLINT,
    load_on            BOOLEAN
);
CREATE INDEX IF NOT EXISTS telemetry_ts_idx ON telemetry(ts DESC);

CREATE TABLE IF NOT EXISTS daily (
    date              DATE PRIMARY KEY,
    batt_v_min        NUMERIC(4,1),
    batt_v_max        NUMERIC(4,1),
    charge_i_max      NUMERIC(5,2),
    discharge_i_max   NUMERIC(5,2),
    charge_w_max      INTEGER,
    discharge_w_max   INTEGER,
    charge_ah         INTEGER,
    discharge_ah      INTEGER,
    generated_wh      INTEGER,
    consumed_wh       INTEGER,
    updated_at        TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS lifetime (
    ts                          TIMESTAMPTZ PRIMARY KEY DEFAULT now(),
    operating_days              INTEGER,
    over_discharges             INTEGER,
    full_charges                INTEGER,
    cumulative_charge_ah        BIGINT,
    cumulative_discharge_ah     BIGINT,
    cumulative_gen_wh           BIGINT,
    cumulative_cons_wh          BIGINT
);

CREATE TABLE IF NOT EXISTS events (
    id          BIGSERIAL PRIMARY KEY,
    ts          TIMESTAMPTZ DEFAULT now(),
    fault_word  INTEGER NOT NULL,
    description TEXT
);
CREATE INDEX IF NOT EXISTS events_ts_idx ON events(ts DESC);
