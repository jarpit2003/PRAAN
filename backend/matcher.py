import os
import asyncio
import json
import math
from datetime import date, datetime, timezone, timedelta
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

AWS_REGION    = os.getenv("AWS_REGION", "us-east-1")
BEDROCK_MODEL = os.getenv("BEDROCK_MODEL", "amazon.nova-micro-v1:0")

# ── Bedrock geocoder ──────────────────────────────────────
# Cache so the same city/area is never geocoded twice in a session
_GEO_CACHE: dict[str, tuple[float, float]] = {}

# Fallback coords for known Indian cities
_CITY_COORDS: dict[str, tuple[float, float]] = {
    "hyderabad": (17.3850, 78.4867),
    "mumbai":    (19.0760, 72.8777),
    "delhi":     (28.6139, 77.2090),
    "new delhi": (28.6139, 77.2090),
    "bengaluru": (12.9716, 77.5946),
    "bangalore": (12.9716, 77.5946),
    "chennai":   (13.0827, 80.2707),
    "pune":      (18.5204, 73.8567),
    "kolkata":   (22.5726, 88.3639),
    "ahmedabad": (23.0225, 72.5714),
    "jaipur":    (26.9124, 75.7873),
    "surat":     (21.1702, 72.8311),
    "lucknow":   (26.8467, 80.9462),
    "kanpur":    (26.4499, 80.3319),
    "nagpur":    (21.1458, 79.0882),
    "patna":     (25.5941, 85.1376),
    "bhopal":    (23.2599, 77.4126),
}


def bedrock_geocode(location_text: str) -> tuple[float, float]:
    """
    Use Amazon Bedrock (Claude) to convert a free-text location
    (city, area, landmark) into (latitude, longitude).

    Falls back to:
      1. In-memory cache
      2. Hardcoded city dict
      3. Default (Hyderabad centroid)
    """
    key = location_text.strip().lower()

    # Cache hit
    if key in _GEO_CACHE:
        return _GEO_CACHE[key]

    # Hardcoded city dict hit
    if key in _CITY_COORDS:
        _GEO_CACHE[key] = _CITY_COORDS[key]
        return _CITY_COORDS[key]

    # Try Bedrock
    try:
        import boto3
        bedrock = boto3.client("bedrock-runtime", region_name=AWS_REGION)
        prompt = f"""You are a geocoding assistant. Convert this Indian location to coordinates.

Location: "{location_text}"

Respond ONLY with valid JSON, no explanation:
{{"latitude": <float>, "longitude": <float>, "resolved_name": "<canonical place name>"}}

If you cannot determine the location, use the nearest major Indian city centroid.
Always return valid JSON with numeric latitude and longitude."""
        body = json.dumps({
            "messages": [{"role": "user", "content": [{"text": prompt}]}]
        })
        resp = bedrock.invoke_model(modelId=BEDROCK_MODEL, body=body)
        raw  = json.loads(resp["body"].read())["output"]["message"]["content"][0]["text"].strip()
        import re
        m = re.search(r'\{.*\}', raw, re.DOTALL)
        if m:
            geo = json.loads(m.group())
            lat = float(geo["latitude"])
            lon = float(geo["longitude"])
            _GEO_CACHE[key] = (lat, lon)
            print(f"[GEOCODE] Bedrock resolved '{location_text}' -> ({lat}, {lon}) [{geo.get('resolved_name','')}]")
            return (lat, lon)
    except Exception as e:
        print(f"[GEOCODE] Bedrock failed for '{location_text}': {e}")

    # Final fallback: Hyderabad
    default = (17.3850, 78.4867)
    _GEO_CACHE[key] = default
    return default


def compute_proximity_score(patient_location: str, donor_lat: float, donor_lon: float) -> tuple[float, float]:
    """
    Geocode the patient's location via Bedrock, then compute:
      distance_km    = Haversine(patient_lat/lon, donor_lat/lon)
      proximity_score = 1 / (1 + distance_km)   [1.0 at 0 km, decays with distance]

    Returns (proximity_score, distance_km)
    """
    pat_lat, pat_lon = bedrock_geocode(patient_location)
    dist_km = _haversine(pat_lat, pat_lon, donor_lat, donor_lon)
    proximity = round(1.0 / (1.0 + dist_km), 6)
    return proximity, round(dist_km, 2)

NEO4J_URI      = os.getenv("NEO4J_URI",      "bolt://localhost:7687")
NEO4J_USER     = os.getenv("NEO4J_USER",     "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

COMPATIBILITY: dict[str, list[str]] = {
    "O-":  ["O-", "O+", "A-", "A+", "B-", "B+", "AB-", "AB+"],
    "O+":  ["O+", "A+", "B+", "AB+"],
    "A-":  ["A-", "A+", "AB-", "AB+"],
    "A+":  ["A+", "AB+"],
    "B-":  ["B-", "B+", "AB-", "AB+"],
    "B+":  ["B+", "AB+"],
    "AB-": ["AB-", "AB+"],
    "AB+": ["AB+"],
}


def _get_driver():
    from neo4j import GraphDatabase
    return GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))


def _neo4j_available() -> bool:
    try:
        driver = _get_driver()
        driver.verify_connectivity()
        driver.close()
        return True
    except Exception:
        return False


# ── Graph setup ───────────────────────────────────────────

def setup_graph(donors: list[dict], patients: list[dict]) -> None:
    driver = _get_driver()
    with driver.session() as session:
        session.run("CREATE CONSTRAINT donor_id IF NOT EXISTS FOR (d:Donor)    REQUIRE d.id IS UNIQUE")
        session.run("CREATE CONSTRAINT patient_id IF NOT EXISTS FOR (p:Patient) REQUIRE p.id IS UNIQUE")
        session.run(
            """
            UNWIND $donors AS row
            MERGE (d:Donor {id: row.id})
            SET d.name=row.name, d.blood_type=row.blood_type, d.city=row.city,
                d.response_score=row.response_score, d.is_active=row.is_active,
                d.last_donation=row.last_donation, d.phone=row.phone
            """,
            donors=[{"id": str(d["id"]), "name": d["name"], "blood_type": d["blood_type"],
                     "city": d["city"], "response_score": float(d.get("response_score") or 5.0),
                     "is_active": bool(d.get("is_active", True)),
                     "last_donation": str(d["last_donation"]) if d.get("last_donation") else None,
                     "phone": d.get("phone", "")} for d in donors],
        )
        session.run(
            """
            UNWIND $patients AS row
            MERGE (p:Patient {id: row.id})
            SET p.name=row.name, p.blood_type=row.blood_type, p.city=row.city
            """,
            patients=[{"id": str(p["id"]), "name": p["name"],
                       "blood_type": p["blood_type"], "city": p["city"]} for p in patients],
        )
        compat_pairs = [{"donor_type": dt, "recipient_type": rt}
                        for dt, recipients in COMPATIBILITY.items() for rt in recipients]
        session.run(
            """
            UNWIND $pairs AS pair
            MATCH (d:Donor   {blood_type: pair.donor_type})
            MATCH (p:Patient {blood_type: pair.recipient_type})
            MERGE (d)-[:CAN_DONATE_TO]->(p)
            """,
            pairs=compat_pairs,
        )
    driver.close()


# ── Neo4j matching ────────────────────────────────────────

def find_best_donors(patient_id: str, limit: int = 5) -> list[dict]:
    driver   = _get_driver()
    today_str = str(date.today())
    query = """
    MATCH (p:Patient {id: $patient_id})<-[:CAN_DONATE_TO]-(d:Donor)
    WHERE d.is_active = true
    WITH d, p,
         CASE WHEN d.city = p.city THEN 0.2 ELSE 0.0 END AS city_bonus,
         CASE WHEN d.last_donation IS NULL THEN 0.2
              WHEN date($today) - date(d.last_donation) > duration({days: 90}) THEN 0.2
              ELSE 0.0 END AS recency_bonus
    WITH d,
         1.0 + (d.response_score * 0.4) + city_bonus + recency_bonus AS match_score,
         CASE WHEN d.last_donation IS NULL THEN null
              ELSE duration.between(date(d.last_donation), date($today)).days
         END AS days_since_donation
    RETURN d.id AS donor_id, d.name AS name, d.phone AS phone,
           d.blood_type AS blood_type, d.city AS city,
           match_score, days_since_donation
    ORDER BY match_score DESC LIMIT $limit
    """
    with driver.session() as session:
        result = session.run(query, patient_id=patient_id, today=today_str, limit=limit)
        rows = [dict(r) for r in result]
    driver.close()
    return rows


# ── Haversine distance (km) ──────────────────────────────

def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    return R * 2 * math.asin(math.sqrt(a))


# ── Blood group normalisation ─────────────────────────────
# donors_v2 stores "A Positive" / "O Negative" etc.
# COMPATIBILITY map uses "A+" / "O-" etc.

_BG_MAP = {
    "a positive": "A+",  "a negative": "A-",
    "b positive": "B+",  "b negative": "B-",
    "o positive": "O+",  "o negative": "O-",
    "ab positive": "AB+", "ab negative": "AB-",
}

def _norm_bg(raw: str) -> str:
    return _BG_MAP.get((raw or "").strip().lower(), raw)


# ── donors_v2 matching (TOPSIS + Haversine) ───────────────

def donors_v2_match(patient, db, limit: int = 5) -> list[dict]:
    """
    Match donors from donors_v2 using:
      final_score = 0.60 * total_score + 0.40 * proximity_score

    Filters:
      - Blood compatibility
      - eligibility_status = 'eligible'
      - bridge_status = TRUE
      - donor_availability_score > 0
    """
    from sqlalchemy import text as sa_text

    patient_bt  = patient.blood_type  # e.g. "A+"
    # Compatible donor blood groups (what donor can have to donate to this patient)
    compatible_donors = [
        donor_bt
        for donor_bt, can_donate_to in COMPATIBILITY.items()
        if patient_bt in can_donate_to
    ]
    # Convert to donors_v2 format e.g. "A Positive"
    _INV_BG_MAP = {v: k.title() for k, v in _BG_MAP.items()}
    compatible_v2 = [_INV_BG_MAP.get(bt, bt) for bt in compatible_donors]

    if not compatible_v2:
        return []

    placeholders = ",".join(f":{i}" for i in range(len(compatible_v2)))
    params = {str(i): bg for i, bg in enumerate(compatible_v2)}
    params["limit"] = limit * 10  # fetch more, score + sort in Python

    rows = db.execute(
        sa_text(f"""
            SELECT user_id, contact_number, blood_group, gender,
                   latitude, longitude, total_score, donor_availability_score,
                   days_since_last_donation, eligibility_status, donor_rank
            FROM donors_v2
            WHERE eligibility_status = 'eligible'
              AND (bridge_status = TRUE OR bridge_status IS NULL)
              AND (donor_availability_score > 0 OR donor_availability_score IS NULL)
              AND blood_group IN ({placeholders})
            ORDER BY total_score DESC
            LIMIT :limit
        """),
        params,
    ).fetchall()

    # ── Geocode patient location via Bedrock ─────────────────
    # Prefer location field (free-text from bot), fall back to city
    patient_location = (
        getattr(patient, "location", None)
        or getattr(patient, "city", None)
        or "Hyderabad"
    )
    pat_lat, pat_lon = bedrock_geocode(patient_location)
    print(f"[MATCHER] Patient location '{patient_location}' -> ({pat_lat}, {pat_lon})")

    scored = []
    for r in rows:
        don_lat = float(r.latitude)  if r.latitude  else pat_lat
        don_lon = float(r.longitude) if r.longitude else pat_lon
        proximity_score, dist_km = compute_proximity_score(patient_location, don_lat, don_lon)
        total_score  = float(r.total_score or 0)
        final_score  = round(0.60 * total_score + 0.40 * proximity_score, 6)
        # user_id may be a hex string or UUID — normalise to str
        raw_uid = r.user_id
        if isinstance(raw_uid, (bytes, memoryview)):
            raw_uid = bytes(raw_uid).hex()
        scored.append({
            "donor_id":            str(raw_uid),
            "name":                f"Donor {(r.contact_number or '')[-4:]}",
            "phone":               r.contact_number or "",
            "blood_type":          _norm_bg(r.blood_group),
            "city":                getattr(patient, "city", ""),
            "match_score":         final_score,
            "final_score":         final_score,
            "days_since_donation": r.days_since_last_donation,
            "distance_km":         round(dist_km, 2),
            "total_score":         total_score,
            "proximity_score":     round(proximity_score, 4),
        })

    scored.sort(key=lambda x: x["match_score"], reverse=True)
    return scored[:limit]


# ── SQL fallback (old donors table) ───────────────────────

def sql_fallback_donors(patient, db, limit: int = 5) -> list[dict]:
    from sqlalchemy import text as sa_text
    today = date.today()
    for city_filter in [patient.city, None]:
        params = {"recipient_type": patient.blood_type, "limit": limit * 4}
        city_clause = "AND d.city = :city" if city_filter else ""
        if city_filter:
            params["city"] = city_filter
        rows = db.execute(
            sa_text(f"""
                SELECT d.id, d.name, d.phone, d.blood_type, d.city,
                       d.response_score, d.last_donation, d.topsis_score
                FROM donors d
                JOIN blood_compatibility bc
                  ON bc.donor_type = d.blood_type AND bc.recipient_type = :recipient_type
                WHERE d.is_active = true {city_clause}
                ORDER BY d.topsis_score DESC LIMIT :limit
            """),
            params,
        ).fetchall()
        if rows:
            break

    patient_location = getattr(patient, "location", None) or getattr(patient, "city", None) or "Delhi"
    pat_lat, pat_lon = bedrock_geocode(patient_location)

    results = []
    for r in rows:
        last_don   = r.last_donation
        days_since: Optional[int] = (today - last_don).days if last_don else None
        topsis     = float(r.topsis_score or 0.5)
        # Proximity score using donor city coords
        donor_city = (r.city or "").lower()
        don_lat, don_lon = _CITY_COORDS.get(donor_city, (pat_lat, pat_lon))
        dist_km    = _haversine(pat_lat, pat_lon, don_lat, don_lon)
        proximity  = round(1.0 / (1.0 + dist_km), 4)
        final_score = round(0.60 * topsis + 0.40 * proximity, 4)
        results.append({
            "donor_id":            str(r.id),
            "name":                r.name,
            "phone":               r.phone,
            "blood_type":          r.blood_type,
            "city":                r.city,
            "match_score":         final_score,
            "topsis_score":        topsis,
            "proximity_score":     proximity,
            "distance_km":         round(dist_km, 2),
            "days_since_donation": days_since,
        })
    results.sort(key=lambda x: x["match_score"], reverse=True)
    return results[:limit]


def match_donors_for_patient(patient, db, limit: int = 5) -> tuple[list[dict], str]:
    # Try Neo4j first
    if _neo4j_available():
        try:
            results = find_best_donors(str(patient.id), limit=limit)
            if results:
                return results, "neo4j"
        except Exception:
            pass
    # Use donors table directly (real data with names + UUIDs)
    results = sql_fallback_donors(patient, db, limit=limit)
    return results, "sql_fallback"


# ── Auto-escalation background task ──────────────────────

async def run_escalation(request_id: str, urgency: str, db_factory):
    """
    4-round automatic escalation after a request is matched.
    Runs entirely in the background via FastAPI BackgroundTasks.

    db_factory: callable that returns a fresh DB session (use SessionLocal)

    Round 1 ( 0 min): already done by trigger_match — top 3 notified
    Round 2 (30 min): notify next 3 if no confirmation
    Round 3 (60 min): notify 5 more + log alert to activity feed
    Round 4 (90 min): if urgent + still unconfirmed → SMS/alert coordinator
    """
    from models import TransfusionRequest, DonorMatch, Donor
    from whatsapp import send_donation_request, _log, ACTIVITY_FEED
    from uuid import UUID

    rounds = [
        (30 * 60, 3, False),   # 30 min → 3 more donors
        (60 * 60, 5, True),    # 60 min → 5 donors + alert
        (90 * 60, 0, False),   # 90 min → coordinator SMS (urgent only)
    ]

    req_uuid = UUID(request_id)

    for wait_secs, donor_count, alert_coordinator in rounds:
        await asyncio.sleep(wait_secs)

        db = db_factory()
        try:
            req = (db.query(TransfusionRequest)
                   .filter(TransfusionRequest.id == req_uuid).first())
            if not req or req.status == "fulfilled":
                return  # resolved, stop escalating

            # Check if any donor confirmed
            confirmed = (db.query(DonorMatch)
                         .filter(DonorMatch.request_id == req_uuid,
                                 DonorMatch.confirmed == True).first())
            if confirmed:
                return  # confirmed, stop escalating

            round_num = rounds.index((wait_secs, donor_count, alert_coordinator)) + 2
            _log(f"Escalation Round {round_num}: no confirmation for request {request_id[:8]}… "
                 f"notifying {donor_count} more donors", "warn")

            if donor_count > 0:
                # Find next unnotified matched donors
                unnotified = (db.query(DonorMatch)
                              .filter(DonorMatch.request_id == req_uuid,
                                      DonorMatch.notified_at == None)
                              .order_by(DonorMatch.match_score.desc())
                              .limit(donor_count).all())

                now = datetime.now(timezone.utc)
                patient = req.patient if hasattr(req, "patient") else None
                if not patient:
                    from models import Patient
                    patient = db.query(Patient).filter(Patient.id == req.patient_id).first()

                for m in unnotified:
                    donor = db.query(Donor).filter(Donor.id == m.donor_id).first()
                    if donor and patient:
                        send_donation_request(
                            {"name": donor.name, "phone": donor.phone,
                             "language": donor.preferred_language,
                             "blood_type": donor.blood_type},
                            {"blood_type": patient.blood_type},
                            request_id,
                        )
                        m.notified_at = now
                db.commit()

            if alert_coordinator:
                _log(f"⚠ ALERT: Request {request_id[:8]} unconfirmed at 60 min — "
                     f"coordinator intervention may be needed", "alert")

            # Round 4: urgent + 90 min → coordinator SMS
            if wait_secs == 90 * 60 and urgency == "urgent":
                coordinator_phone = os.getenv("COORDINATOR_PHONE", "")
                if coordinator_phone:
                    from whatsapp import _send
                    _send(coordinator_phone,
                          f"🚨 PRAAN ALERT: Urgent blood request {request_id[:8]} "
                          f"has no donor confirmed after 90 minutes. Immediate action needed.")
                _log(f"🚨 CRITICAL: 90-min SLA breach for urgent request {request_id[:8]}. "
                     f"Coordinator SMS sent.", "alert")

        finally:
            db.close()
