"""
load_donors_v2.py — loads DatasetBlend_final_with_scores1.csv into donors_v2 table.
Run once: python load_donors_v2.py
"""
import os
import csv
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DB_URL = os.getenv("DATABASE_URL", "postgresql://postgres:root%4039@localhost:5432/praan_db")
CSV_PATH = os.path.join(os.path.dirname(__file__), "..", "DatasetBlend_final_with_scores1.csv")

CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS donors_v2 (
    id                             SERIAL PRIMARY KEY,
    user_id                        TEXT,
    bridge_id                      TEXT,
    role                           TEXT,
    role_status                    BOOLEAN,
    bridge_status                  BOOLEAN,
    blood_group                    TEXT,
    gender                         TEXT,
    latitude                       DOUBLE PRECISION,
    longitude                      DOUBLE PRECISION,
    bridge_gender                  TEXT,
    bridge_blood_group             TEXT,
    quantity_required              INTEGER,
    last_transfusion_date          TEXT,
    expected_next_transfusion_date TEXT,
    registration_date              TEXT,
    donor_type                     TEXT,
    last_contacted_date            TEXT,
    last_donation_date             TEXT,
    next_eligible_date             TEXT,
    donations_till_date            INTEGER,
    eligibility_status             TEXT,
    cycle_of_donations             INTEGER,
    total_calls                    INTEGER,
    frequency_in_days              INTEGER,
    status_of_bridge               BOOLEAN,
    status                         TEXT,
    donated_earlier                BOOLEAN,
    last_bridge_donation_date      TEXT,
    calls_to_donations_ratio       DOUBLE PRECISION,
    user_donation_active_status    TEXT,
    inactive_trigger_comment       TEXT,
    response_rate                  DOUBLE PRECISION,
    active_score                   DOUBLE PRECISION,
    days_since_last_donation       INTEGER,
    donor_availability_score       DOUBLE PRECISION,
    donor_rank                     INTEGER,
    total_score                    DOUBLE PRECISION,
    contact_number                 TEXT
);
"""

INSERT_SQL = """
INSERT INTO donors_v2 (
    user_id, bridge_id, role, role_status, bridge_status, blood_group, gender,
    latitude, longitude, bridge_gender, bridge_blood_group, quantity_required,
    last_transfusion_date, expected_next_transfusion_date, registration_date,
    donor_type, last_contacted_date, last_donation_date, next_eligible_date,
    donations_till_date, eligibility_status, cycle_of_donations, total_calls,
    frequency_in_days, status_of_bridge, status, donated_earlier,
    last_bridge_donation_date, calls_to_donations_ratio, user_donation_active_status,
    inactive_trigger_comment, response_rate, active_score, days_since_last_donation,
    donor_availability_score, donor_rank, total_score, contact_number
) VALUES (
    %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
    %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s
)
"""

def parse_bool(val):
    if val is None or val.strip() == "":
        return None
    return val.strip().upper() in ("TRUE", "1", "YES")

def parse_int(val):
    try:
        return int(float(val.strip())) if val.strip() else None
    except:
        return None

def parse_float(val):
    try:
        return float(val.strip()) if val.strip() else None
    except:
        return None

def parse_text(val):
    v = val.strip() if val else ""
    return v if v else None

def main():
    conn = psycopg2.connect(DB_URL)
    cur  = conn.cursor()

    print("Creating donors_v2 table...")
    cur.execute(CREATE_TABLE)
    conn.commit()

    print(f"Loading CSV: {CSV_PATH}")
    loaded = 0
    errors = 0

    with open(CSV_PATH, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                cur.execute(INSERT_SQL, (
                    parse_text(row["user_id"]),
                    parse_text(row["bridge_id"]),
                    parse_text(row["role"]),
                    parse_bool(row["role_status"]),
                    parse_bool(row["bridge_status"]),
                    parse_text(row["blood_group"]),
                    parse_text(row["gender"]),
                    parse_float(row["latitude"]),
                    parse_float(row["longitude"]),
                    parse_text(row["bridge_gender"]),
                    parse_text(row["bridge_blood_group"]),
                    parse_int(row["quantity_required"]),
                    parse_text(row["last_transfusion_date"]),
                    parse_text(row["expected_next_transfusion_date"]),
                    parse_text(row["registration_date"]),
                    parse_text(row["donor_type"]),
                    parse_text(row["last_contacted_date"]),
                    parse_text(row["last_donation_date"]),
                    parse_text(row["next_eligible_date"]),
                    parse_int(row["donations_till_date"]),
                    parse_text(row["eligibility_status"]),
                    parse_int(row["cycle_of_donations"]),
                    parse_int(row["total_calls"]),
                    parse_int(row["frequency_in_days"]),
                    parse_bool(row["status_of_bridge"]),
                    parse_text(row["status"]),
                    parse_bool(row["donated_earlier"]),
                    parse_text(row["last_bridge_donation_date"]),
                    parse_float(row["calls_to_donations_ratio"]),
                    parse_text(row["user_donation_active_status"]),
                    parse_text(row["inactive_trigger_comment"]),
                    parse_float(row["response_rate"]),
                    parse_float(row["active_score"]),
                    parse_int(row["days_since_last_donation"]),
                    parse_float(row["donor_availability_score"]),
                    parse_int(row["donor_rank"]),
                    parse_float(row["total_score"]),
                    parse_text(row["contact_number"]),
                ))
                loaded += 1
            except Exception as e:
                errors += 1
                print(f"  Row error: {e} | user_id={row.get('user_id','?')[:20]}")
                conn.rollback()
                continue
            if loaded % 100 == 0:
                conn.commit()
                print(f"  {loaded} rows loaded...")

    conn.commit()
    cur.close()
    conn.close()
    print(f"\nDone. Loaded: {loaded} | Errors: {errors}")

if __name__ == "__main__":
    main()
