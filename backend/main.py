import asyncio
from datetime import date, datetime, timezone, timedelta
from typing import List
from uuid import UUID

from fastapi import FastAPI, Depends, HTTPException, status, Form, BackgroundTasks
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import func, text
from sqlalchemy.orm import Session, joinedload
from models import Base, engine, get_db, Patient, Donor, TransfusionRequest, DonorMatch
from schemas import PatientOut, DonorOut, RequestCreate, RequestOut, MatchOut, StatsOut, PredictionOut, RequestDetailOut, MatchDetailOut, CriticalCaseOut, ScoredDonorOut
from predictor import predict_next_transfusion
from matcher import match_donors_for_patient, setup_graph, run_escalation
from whatsapp import (
    send_donation_request, send_impact_message,
    simulate_whatsapp_flow,
    _confirm_match_by_phone, _decline_match_by_phone,
    _YES_WORDS, _NO_WORDS, _CONFIRM_MSG, _DECLINE_MSG,
    handle_patient_message, ACTIVITY_FEED,
)
from ivr import handle_ivr_call
from models import SessionLocal

app = FastAPI(title="PRAAN API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://*.amplifyapp.com"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Startup ───────────────────────────────────────────────

@app.on_event("startup")
def startup():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            # Add raised_by column if it doesn't exist (safe migration)
            conn.execute(text("""
                ALTER TABLE transfusion_requests
                ADD COLUMN IF NOT EXISTS raised_by VARCHAR(20) DEFAULT 'coordinator'
            """))
            conn.commit()
        print("PRAAN API running  |  DB connection: OK")
    except Exception as e:
        print(f"PRAAN API running  |  DB connection: FAILED ({e})")


# ── Patients ──────────────────────────────────────────────

@app.get("/patients", response_model=List[PatientOut])
def list_patients(db: Session = Depends(get_db)):
    return db.query(Patient).order_by(Patient.name).all()


@app.get("/patients/{patient_id}", response_model=PatientOut)
def get_patient(patient_id: UUID, db: Session = Depends(get_db)):
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    return patient


# ── Transfusion Requests ──────────────────────────────────

@app.post("/requests", response_model=RequestOut, status_code=status.HTTP_201_CREATED)
def create_request(body: RequestCreate, db: Session = Depends(get_db)):
    if not db.query(Patient).filter(Patient.id == body.patient_id).first():
        raise HTTPException(status_code=404, detail="Patient not found")

    valid_urgency = {"urgent", "normal", "planned"}
    if body.urgency not in valid_urgency:
        raise HTTPException(status_code=422, detail=f"urgency must be one of {valid_urgency}")

    req = TransfusionRequest(**body.model_dump())
    db.add(req)
    db.commit()
    db.refresh(req)
    return db.query(TransfusionRequest).options(joinedload(TransfusionRequest.patient)).filter(
        TransfusionRequest.id == req.id
    ).first()


@app.get("/requests", response_model=List[RequestOut])
def list_requests(db: Session = Depends(get_db)):
    return (
        db.query(TransfusionRequest)
        .options(joinedload(TransfusionRequest.patient))
        .order_by(TransfusionRequest.created_at.desc())
        .all()
    )


@app.get("/requests/{request_id}", response_model=RequestDetailOut)
def get_request(request_id: UUID, db: Session = Depends(get_db)):
    req = (
        db.query(TransfusionRequest)
        .options(joinedload(TransfusionRequest.patient))
        .filter(TransfusionRequest.id == request_id)
        .first()
    )
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")

    matches_raw = (
        db.query(DonorMatch)
        .options(joinedload(DonorMatch.donor))
        .filter(DonorMatch.request_id == request_id)
        .order_by(DonorMatch.match_score.desc())
        .all()
    )
    matches = []
    for i, m in enumerate(matches_raw):
        reasons = []
        d = m.donor
        if d:
            reasons.append("✓ Compatible blood group")
            if d.is_active:
                reasons.append("✓ Active donor")
            if d.last_donation:
                days = (date.today() - d.last_donation).days
                if days > 90:
                    reasons.append(f"✓ Last donated {days} days ago — eligible")
            if req.patient and d.city == req.patient.city:
                reasons.append("✓ Located in same city")
            if d.response_score and d.response_score >= 7:
                reasons.append("✓ Strong donation history")
        matches.append(MatchDetailOut(
            id=m.id, donor_id=m.donor_id, match_score=m.match_score,
            confirmed=m.confirmed, confirmed_at=m.confirmed_at,
            notified_at=m.notified_at, rank=i+1, donor=d, reasons=reasons
        ))

    return RequestDetailOut(
        id=req.id, patient_id=req.patient_id, predicted_date=req.predicted_date,
        urgency=req.urgency, status=req.status, notes=req.notes,
        raised_by=getattr(req, "raised_by", "coordinator"),
        created_at=req.created_at, patient=req.patient, matches=matches
    )


# ── Patient register (used by Veeru bot) ─────────────────

class PatientRegister(BaseModel):
    name:       str
    blood_type: str
    city:       str
    phone:      str

CITY_MAP = {
    "1": "Delhi", "2": "Mumbai", "3": "Bengaluru",
    "4": "Chennai", "5": "Hyderabad",
}

VALID_BLOOD_TYPES = {"O+","O-","A+","A-","B+","B-","AB+","AB-"}

@app.post("/patients/register", response_model=PatientOut, status_code=201)
def register_patient(body: PatientRegister, db: Session = Depends(get_db)):
    import uuid as _uuid
    city       = CITY_MAP.get(body.city, body.city)
    blood_type = body.blood_type.strip().upper()
    if blood_type not in VALID_BLOOD_TYPES:
        raise HTTPException(status_code=422, detail=f"Invalid blood_type: {blood_type}")
    existing = db.query(Patient).filter(
        Patient.name == body.name,
        Patient.city == city,
        Patient.blood_type == blood_type,
    ).first()
    if existing:
        return existing
    p = Patient(
        id               = _uuid.uuid4(),
        name             = body.name,
        blood_type       = blood_type,
        city             = city,
        thalassemia_type = "beta-major",
    )
    try:
        db.add(p)
        db.commit()
        db.refresh(p)
    except Exception as e:
        db.rollback()
        print(f"[REGISTER ERROR] {e}")
        raise HTTPException(status_code=500, detail=str(e))
    from whatsapp import _log
    _log(f"Patient {p.name} registered via Veeru bot ({body.phone})", "info")
    return p


@app.get("/patients/by-phone/{phone}", response_model=PatientOut)
def get_patient_by_phone(phone: str, db: Session = Depends(get_db)):
    """
    Look up a patient by their WhatsApp phone number.
    The bot calls this to check if a caller is already registered.
    Phone is stored in TransfusionRequest.notes as 'bot_phone:<number>'.
    """
    req = (
        db.query(TransfusionRequest)
        .filter(TransfusionRequest.notes.like(f"%bot_phone:{phone}%"))
        .order_by(TransfusionRequest.created_at.desc())
        .first()
    )
    if req:
        patient = db.query(Patient).filter(Patient.id == req.patient_id).first()
        if patient:
            return patient
    raise HTTPException(status_code=404, detail="Patient not found")


@app.post("/bot/request", status_code=201)
def bot_create_request(body: dict, db: Session = Depends(get_db)):
    """
    Single endpoint the Veeru bot calls after urgency is chosen.
    Accepts: { patient_id, urgency, phone }
    Creates request + triggers matching + returns request_id.
    """
    import uuid as _uuid
    from datetime import date, timedelta
    from whatsapp import _log

    patient_id = body.get("patient_id")
    urgency    = body.get("urgency", "normal")
    phone      = body.get("phone", "")
    location   = body.get("location", "")   # free-text from bot e.g. "Banjara Hills, Hyderabad"

    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    # Attach location so matcher can geocode it via Bedrock
    patient.location = location or patient.city

    days_ahead = 1 if urgency == "urgent" else 7
    req = TransfusionRequest(
        id             = _uuid.uuid4(),
        patient_id     = patient.id,
        predicted_date = date.today() + timedelta(days=days_ahead),
        urgency        = urgency,
        status         = "pending",
        notes          = f"bot_phone:{phone}",
        raised_by      = "whatsapp",
    )
    db.add(req)
    db.commit()
    db.refresh(req)

    # Trigger matching immediately
    scored_donors, source = match_donors_for_patient(patient, db, limit=5)
    print(f"[FLOW1] Matching source: {source} | found {len(scored_donors)} donors")
    now = datetime.now(timezone.utc)
    for entry in scored_donors[:3]:
        donor_uuid = None
        try:
            donor_uuid = UUID(entry["donor_id"])
        except Exception:
            donor = db.query(Donor).filter(Donor.phone == entry.get("phone", "")).first()
            if donor:
                donor_uuid = donor.id
        if not donor_uuid:
            continue
        existing = db.query(DonorMatch).filter(
            DonorMatch.request_id == req.id,
            DonorMatch.donor_id   == donor_uuid,
        ).first()
        if existing:
            continue
        db.add(DonorMatch(
            request_id  = req.id,
            donor_id    = donor_uuid,
            match_score = round(entry["match_score"], 2),
            notified_at = now,
        ))
        donor = db.query(Donor).filter(Donor.id == donor_uuid).first()
    req.status = "matched"
    db.commit()
    _log(f"Patient {patient.name} raised {urgency} request via Veeru bot ({phone})", "info")

    return {"request_id": str(req.id), "status": "matched", "patient": patient.name}


# ── Donors ───────────────────────────────────────────────

@app.get("/donors", response_model=List[DonorOut])
def list_donors(db: Session = Depends(get_db)):
    return db.query(Donor).order_by(Donor.name).all()


class DonorRegister(BaseModel):
    name:               str
    blood_type:         str
    city:               str
    phone:              str
    gender:             str = ""
    donated_earlier:    bool = False
    last_donation_date: str | None = None

@app.post("/donors/register", response_model=DonorOut, status_code=201)
def register_donor(body: DonorRegister, db: Session = Depends(get_db)):
    import uuid as _uuid
    from whatsapp import _log
    blood_type = body.blood_type.strip().upper()
    if blood_type not in VALID_BLOOD_TYPES:
        raise HTTPException(status_code=422, detail=f"Invalid blood_type: {blood_type}")
    existing = db.query(Donor).filter(Donor.phone == body.phone).first()
    if existing:
        return existing
    city = CITY_MAP.get(body.city, body.city)
    d = Donor(
        id                 = _uuid.uuid4(),
        name               = body.name,
        phone              = body.phone,
        blood_type         = blood_type,
        city               = city,
        preferred_language = "en",
        is_active          = True,
        last_donation      = body.last_donation_date or None,
        topsis_score       = 0.5,
    )
    db.add(d)
    db.commit()
    db.refresh(d)

    _log(f"Donor {d.name} registered via Veeru bot ({body.phone})", "info")
    return d


# ── Matching ──────────────────────────────────────────────

@app.post("/requests/{request_id}/match/run", response_model=List[ScoredDonorOut])
def run_donor_matching(request_id: UUID, db: Session = Depends(get_db)):
    """
    Flow 2 — Full donor matching pipeline:
      1. Blood compatibility filter
      2. Eligibility + active donor filter
      3. Proximity score  = Bedrock geocode + Haversine  (40% weight)
      4. Total score      = TOPSIS from dataset           (60% weight)
      5. Final score      = 0.60 * total_score + 0.40 * proximity_score
      6. Sort by final score → persist top 3 as DonorMatch rows
    Returns all scored candidates with full breakdown.
    """
    from matcher import match_donors_for_patient

    req = (
        db.query(TransfusionRequest)
        .options(joinedload(TransfusionRequest.patient))
        .filter(TransfusionRequest.id == request_id)
        .first()
    )
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")

    patient = req.patient
    if not getattr(patient, "location", None):
        patient.location = patient.city

    scored, source = match_donors_for_patient(patient, db, limit=10)
    print(f"[FLOW2] Source: {source} | Scored {len(scored)} donors")
    if not scored:
        raise HTTPException(status_code=404, detail="No compatible donors found")

    # Persist top 3
    now = datetime.now(timezone.utc)
    for entry in scored[:3]:
        donor_uuid = None
        try:
            donor_uuid = UUID(entry["donor_id"])
        except Exception:
            # donors_v2 user_id is not a UUID — look up by phone in donors table
            donor = db.query(Donor).filter(Donor.phone == entry["phone"]).first()
            if donor:
                donor_uuid = donor.id
        if not donor_uuid:
            continue
        existing = db.query(DonorMatch).filter(
            DonorMatch.request_id == request_id,
            DonorMatch.donor_id   == donor_uuid,
        ).first()
        if not existing:
            db.add(DonorMatch(
                request_id  = request_id,
                donor_id    = donor_uuid,
                match_score = round(entry.get("final_score", entry.get("match_score", 0)), 2),
                notified_at = now,
            ))
    req.status = "matched"
    db.commit()

    return [
        ScoredDonorOut(
            rank            = i + 1,
            donor_id        = e["donor_id"],
            name            = e["name"],
            phone           = e["phone"],
            blood_type      = e["blood_type"],
            distance_km     = e.get("distance_km", 0),
            total_score     = e.get("total_score", e.get("match_score", 0)),
            proximity_score = e.get("proximity_score", 0),
            final_score     = e.get("final_score", e.get("match_score", 0)),
            days_since_donation = e.get("days_since_donation"),
        )
        for i, e in enumerate(scored)
    ]


@app.post("/requests/{request_id}/match", response_model=List[MatchOut])
def trigger_match(request_id: UUID, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    req = (
        db.query(TransfusionRequest)
        .options(joinedload(TransfusionRequest.patient))
        .filter(TransfusionRequest.id == request_id)
        .first()
    )
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")

    patient = req.patient
    scored_donors, source = match_donors_for_patient(patient, db, limit=5)

    if not scored_donors:
        raise HTTPException(status_code=404, detail="No compatible donors found")

    now = datetime.now(timezone.utc)
    # Persist top 3 as DonorMatch records in PostgreSQL
    for entry in scored_donors[:3]:
        try:
            donor_uuid = UUID(entry["donor_id"])
        except (ValueError, AttributeError):
            continue
        existing = db.query(DonorMatch).filter(
            DonorMatch.request_id == request_id,
            DonorMatch.donor_id   == donor_uuid,
        ).first()
        if existing:
            continue
        db.add(DonorMatch(
            request_id  = request_id,
            donor_id    = donor_uuid,
            match_score = round(entry["match_score"], 2),
            notified_at = now,
        ))

    req.status = "matched"
    db.commit()

    background_tasks.add_task(run_escalation, str(request_id), req.urgency, SessionLocal)

    return (
        db.query(DonorMatch)
        .options(joinedload(DonorMatch.donor))
        .filter(DonorMatch.request_id == request_id)
        .all()
    )


# ── Confirm Match ─────────────────────────────────────────

@app.patch("/matches/{match_id}/confirm", response_model=MatchOut)
def confirm_match(match_id: UUID, db: Session = Depends(get_db)):
    match = (
        db.query(DonorMatch)
        .options(joinedload(DonorMatch.donor))
        .filter(DonorMatch.id == match_id)
        .first()
    )
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    if match.confirmed:
        raise HTTPException(status_code=409, detail="Match already confirmed")

    match.confirmed    = True
    match.confirmed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(match)
    return match


# ── Prediction ────────────────────────────────────────

def _patient_to_predictor_input(p: Patient) -> dict:
    return {
        "last_hb":          float(p.hemoglobin_level) if p.hemoglobin_level is not None else None,
        "last_transfusion": p.last_transfusion,
        "thal_type":        p.thalassemia_type,
    }


@app.get("/predict/{patient_id}", response_model=PredictionOut)
def predict_patient(patient_id: UUID, db: Session = Depends(get_db)):
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    result = predict_next_transfusion(_patient_to_predictor_input(patient))
    return PredictionOut(patient_id=patient.id, patient_name=patient.name, **result)


URGENCY_ORDER = {"urgent": 0, "normal": 1, "planned": 2}


@app.post("/predict/bulk", response_model=List[PredictionOut])
def predict_bulk(db: Session = Depends(get_db)):
    patients = db.query(Patient).all()
    results = []
    for p in patients:
        result = predict_next_transfusion(_patient_to_predictor_input(p))
        results.append(PredictionOut(patient_id=p.id, patient_name=p.name, **result))
    results.sort(key=lambda r: (URGENCY_ORDER.get(r.urgency, 9), r.days_until_needed))
    return results


# ── WhatsApp notifications ───────────────────────────────

@app.post("/notify/{request_id}")
def notify_top_donor(request_id: UUID, db: Session = Depends(get_db)):
    """
    Send a WhatsApp donation request to the top unnotified matched donor
    for a given transfusion request.
    """
    top_match = (
        db.query(DonorMatch)
        .options(joinedload(DonorMatch.donor))
        .filter(
            DonorMatch.request_id  == request_id,
            DonorMatch.confirmed   == False,
            DonorMatch.notified_at == None,
        )
        .order_by(DonorMatch.match_score.desc())
        .first()
    )
    if not top_match:
        raise HTTPException(status_code=404, detail="No unnotified donor match found for this request")

    req = db.query(TransfusionRequest).options(
        joinedload(TransfusionRequest.patient)
    ).filter(TransfusionRequest.id == request_id).first()

    donor   = top_match.donor
    patient = req.patient

    result = send_donation_request(
        donor   = {"name": donor.name, "phone": donor.phone,
                   "language": donor.preferred_language, "blood_type": donor.blood_type},
        patient = {"blood_type": patient.blood_type},
        request_id = str(request_id),
    )

    top_match.notified_at = datetime.now(timezone.utc)
    db.commit()
    return {"sent": True, "donor": donor.name, "sid": result.get("sid")}


@app.post("/whatsapp/reply")
def whatsapp_reply(
    Body: str = Form(...),
    From: str = Form(...),
    db: Session = Depends(get_db),
):
    """
    Twilio webhook — receives inbound WhatsApp replies.
    From format: whatsapp:+91XXXXXXXXXX
    """
    # Parse phone from "whatsapp:+91XXXXXXXXXX"
    phone = From.replace("whatsapp:", "").strip()
    reply = Body.strip().lower()

    if reply in _YES_WORDS:
        ok, match = _confirm_match_by_phone(phone, db)
        if not ok:
            return {"status": "no_pending_match", "phone": phone}

        donor = db.query(Donor).filter(Donor.id == match.donor_id).first()
        lang  = (donor.preferred_language or "en").lower()
        lang  = lang if lang in _CONFIRM_MSG else "en"
        send_donation_request   # already notified; send confirmation
        confirmation_body = _CONFIRM_MSG[lang].format(name=donor.name)
        from whatsapp import _send
        _send(phone, confirmation_body)
        return {"status": "confirmed", "donor": donor.name}

    elif reply in _NO_WORDS:
        ok, next_match = _decline_match_by_phone(phone, db)
        if not ok:
            return {"status": "no_next_donor", "phone": phone}

        # Notify the next donor
        next_donor = db.query(Donor).filter(Donor.id == next_match.donor_id).first()
        req = db.query(TransfusionRequest).options(
            joinedload(TransfusionRequest.patient)
        ).filter(TransfusionRequest.id == next_match.request_id).first()

        # Acknowledge decliner
        decliner = db.query(Donor).filter(Donor.phone == phone).first()
        if decliner:
            lang = (decliner.preferred_language or "en").lower()
            lang = lang if lang in _DECLINE_MSG else "en"
            from whatsapp import _send
            _send(phone, _DECLINE_MSG[lang].format(name=decliner.name))

        send_donation_request(
            donor   = {"name": next_donor.name, "phone": next_donor.phone,
                       "language": next_donor.preferred_language, "blood_type": next_donor.blood_type},
            patient = {"blood_type": req.patient.blood_type},
            request_id = str(next_match.request_id),
        )
        next_match.notified_at = datetime.now(timezone.utc)
        db.commit()
        return {"status": "next_donor_notified", "donor": next_donor.name}

    return {"status": "unrecognised_reply", "body": Body}


# ── Patient WhatsApp bot ──────────────────────────────────

@app.post("/whatsapp/patient")
def whatsapp_patient(
    Body: str = Form(...),
    From: str = Form(...),
    db: Session = Depends(get_db),
):
    """
    Patient/family-facing bot entry point.
    Handles the full conversational flow: menu → lookup → request creation.
    """
    phone = From.replace("whatsapp:", "").strip()
    reply = handle_patient_message(phone, Body, db)
    # Return TwiML-compatible plain text (Twilio reads the body back)
    return {"reply": reply}


# ── IVR endpoints ─────────────────────────────────────────

class IVRRequest(BaseModel):
    phone:    str
    keypress: str

@app.post("/ivr/incoming")
def ivr_incoming(body: IVRRequest, db: Session = Depends(get_db)):
    """
    Simulated IVR endpoint.
    In production: replace with Exotel/Twilio Voice webhook.
    """
    result = handle_ivr_call(body.phone, body.keypress, db)
    return result


# ── Activity feed ─────────────────────────────────────────

@app.get("/activity")
def get_activity(limit: int = 50):
    """
    Returns the last N auto-triggered actions for the coordinator dashboard.
    """
    feed = sorted(ACTIVITY_FEED, key=lambda x: x["ts"], reverse=True)[:limit]
    return [{"ts": e["ts"].isoformat(), "msg": e["msg"], "type": e["type"]} for e in feed]


# ── Critical cases ───────────────────────────────────────

@app.get("/critical", response_model=List[CriticalCaseOut])
def get_critical(db: Session = Depends(get_db)):
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=1)
    reqs = (
        db.query(TransfusionRequest)
        .options(joinedload(TransfusionRequest.patient))
        .filter(
            TransfusionRequest.status.in_(["pending", "matched"]),
            TransfusionRequest.created_at <= cutoff,
        ).all()
    )
    result = []
    for req in reqs:
        confirmed = db.query(DonorMatch).filter(
            DonorMatch.request_id == req.id, DonorMatch.confirmed == True
        ).first()
        if confirmed:
            continue
        age = int((datetime.now(timezone.utc) -
                   req.created_at.replace(tzinfo=timezone.utc)).total_seconds() / 60)
        reason = "No donor confirmed after 90+ min" if age >= 90 else \
                 "No donor response after 30 min" if age >= 30 else "Urgent — no donor yet"
        stage  = "Escalated" if age >= 90 else "Contacting Donors" if req.status == "matched" else "Matching"
        result.append(CriticalCaseOut(
            id=str(req.id),
            patient=req.patient.name if req.patient else "—",
            blood_type=req.patient.blood_type if req.patient else "—",
            city=req.patient.city if req.patient else "—",
            urgency=req.urgency,
            status=req.status,
            waiting_minutes=age,
            reason=reason,
            current_stage=stage,
            raised_by=getattr(req, "raised_by", "coordinator"),
        ))
    return sorted(result, key=lambda x: x.waiting_minutes, reverse=True)


@app.post("/requests/{request_id}/escalate")
def escalate_request(request_id: UUID, db: Session = Depends(get_db)):
    from whatsapp import _log
    req = db.query(TransfusionRequest).filter(TransfusionRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    req.status = "escalated"
    db.commit()
    _log(f"Request {str(request_id)[:8]} manually escalated by coordinator", "alert")
    return {"status": "escalated", "request_id": str(request_id)}


@app.post("/requests/{request_id}/contact-blood-bank")
async def contact_blood_bank(request_id: UUID, db: Session = Depends(get_db)):
    import smtplib, os, boto3, json
    from email.mime.text import MIMEText
    from whatsapp import _log

    req = (
        db.query(TransfusionRequest)
        .options(joinedload(TransfusionRequest.patient))
        .filter(TransfusionRequest.id == request_id)
        .first()
    )
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")

    p = req.patient
    age_mins = int((datetime.now(timezone.utc) -
                    req.created_at.replace(tzinfo=timezone.utc)).total_seconds() / 60)

    # ── Generate email body via Amazon Bedrock ─────────────
    context = (
        f"Patient name: {p.name if p else 'Unknown'}\n"
        f"Blood type needed: {p.blood_type if p else 'Unknown'}\n"
        f"City: {p.city if p else 'Unknown'}\n"
        f"Urgency: {req.urgency}\n"
        f"Waiting time: {age_mins} minutes\n"
        f"Request ID: {str(request_id)}\n"
        f"Condition: Thalassemia patient, no compatible donor confirmed yet."
    )
    prompt = (
        f"You are a medical coordinator at PRAAN, a thalassemia patient support system. "
        f"Write a concise, professional, and urgent email to a blood bank requesting immediate blood supply. "
        f"Use the details below. Be direct, compassionate, and include all key details clearly.\n\n"
        f"{context}\n\n"
        f"Write only the email body (no subject line, no extra commentary)."
    )
    try:
        bedrock = boto3.client(
            "bedrock-runtime",
            region_name=os.getenv("AWS_REGION", "us-east-1"),
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        )
        import asyncio as _asyncio
        resp = await _asyncio.get_event_loop().run_in_executor(None, lambda: bedrock.invoke_model(
            modelId=os.getenv("BEDROCK_MODEL", "amazon.nova-micro-v1:0"),
            body=json.dumps({
                "messages": [{"role": "user", "content": [{"text": prompt}]}]
            }),
        ))
        email_body = json.loads(resp["body"].read())["output"]["message"]["content"][0]["text"].strip()
    except Exception as e:
        print(f"[BEDROCK EMAIL] Failed: {e} — falling back to template")
        email_body = (
            f"Dear Blood Bank Team,\n\n"
            f"We urgently require blood for a thalassemia patient. Details below:\n\n"
            f"  Patient : {p.name if p else '—'}\n"
            f"  Blood Type : {p.blood_type if p else '—'}\n"
            f"  City : {p.city if p else '—'}\n"
            f"  Urgency : {req.urgency.upper()}\n"
            f"  Waiting : {age_mins} minutes\n"
            f"  Request ID : {str(request_id)}\n\n"
            f"No compatible donor has confirmed. Please arrange blood immediately.\n\n"
            f"Regards,\nPRAAN Coordinator"
        )

    # ── Send via SMTP ──────────────────────────────────────
    smtp_host  = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port  = int(os.getenv("SMTP_PORT", 587))
    smtp_user  = os.getenv("SMTP_USER", "")
    smtp_pass  = os.getenv("SMTP_PASS", "")
    to_email   = os.getenv("BLOOD_BANK_EMAIL", "")
    from_email = os.getenv("FROM_EMAIL", smtp_user)

    if not all([smtp_user, smtp_pass, to_email]):
        raise HTTPException(status_code=500, detail="Email not configured. Set SMTP_USER, SMTP_PASS, BLOOD_BANK_EMAIL in .env")

    msg = MIMEText(email_body)
    msg["Subject"] = f"🚨 Urgent Blood Request — {p.blood_type if p else '?'} needed in {p.city if p else '?'}"
    msg["From"]    = from_email
    msg["To"]      = to_email

    try:
        import asyncio as _asyncio
        def _send_email():
            with smtplib.SMTP(smtp_host, smtp_port, timeout=20) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(smtp_user, smtp_pass)
                server.sendmail(from_email, to_email, msg.as_string())
        await _asyncio.get_event_loop().run_in_executor(None, _send_email)
    except Exception as e:
        print(f"[EMAIL ERROR] {type(e).__name__}: {e}")
        raise HTTPException(status_code=500, detail=f"Email failed: {type(e).__name__}: {e}")

    _log(f"Blood bank contacted via AI-generated email for {p.name if p else request_id} ({p.blood_type if p else '?'})", "alert")
    return {"sent": True, "to": to_email}


@app.post("/requests/{request_id}/assign")
def assign_donor(request_id: UUID, body: dict, db: Session = Depends(get_db)):
    from whatsapp import _log, send_donation_request
    donor_id = body.get("donor_id")
    if not donor_id:
        raise HTTPException(status_code=422, detail="donor_id required")
    req = db.query(TransfusionRequest).options(
        joinedload(TransfusionRequest.patient)
    ).filter(TransfusionRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    donor = db.query(Donor).filter(Donor.id == UUID(donor_id)).first()
    if not donor:
        raise HTTPException(status_code=404, detail="Donor not found")
    existing = db.query(DonorMatch).filter(
        DonorMatch.request_id == request_id, DonorMatch.donor_id == donor.id
    ).first()
    if not existing:
        db.add(DonorMatch(
            request_id=request_id, donor_id=donor.id,
            match_score=0, notified_at=datetime.now(timezone.utc)
        ))
        db.commit()
    send_donation_request(
        {"name": donor.name, "phone": donor.phone,
         "language": donor.preferred_language, "blood_type": donor.blood_type},
        {"blood_type": req.patient.blood_type}, str(request_id)
    )
    _log(f"Donor {donor.name} manually assigned to request {str(request_id)[:8]} by coordinator", "info")
    return {"status": "assigned", "donor": donor.name}


@app.get("/exceptions")
def get_exceptions(db: Session = Depends(get_db)):
    """
    Requests where no donor confirmed after 60+ minutes.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=60)
    pending_old = (
        db.query(TransfusionRequest)
        .options(joinedload(TransfusionRequest.patient))
        .filter(
            TransfusionRequest.status.in_(["pending", "matched"]),
            TransfusionRequest.created_at <= cutoff,
        ).all()
    )
    result = []
    for req in pending_old:
        confirmed = db.query(DonorMatch).filter(
            DonorMatch.request_id == req.id,
            DonorMatch.confirmed  == True,
        ).first()
        if not confirmed:
            age_mins = int((datetime.now(timezone.utc) -
                            req.created_at.replace(tzinfo=timezone.utc)).total_seconds() / 60)
            result.append({
                "id":          str(req.id),
                "patient":     req.patient.name if req.patient else "—",
                "blood_type":  req.patient.blood_type if req.patient else "—",
                "urgency":     req.urgency,
                "status":      req.status,
                "age_minutes": age_mins,
                "raised_by":   getattr(req, "raised_by", "coordinator"),
            })
    return sorted(result, key=lambda x: x["age_minutes"], reverse=True)


# ── Stats ─────────────────────────────────────────────────

@app.get("/debug", response_model=None, include_in_schema=False)
def debug_logs():
    """Live log viewer — open in browser."""
    return HTMLResponse(content="""
<!DOCTYPE html><html lang="en">
<head><meta charset="UTF-8"><title>PRAAN Logs</title>
<style>
  *{box-sizing:border-box;margin:0;padding:0}
  body{background:#0d1117;color:#c9d1d9;font-family:monospace;font-size:13px}
  header{background:#161b22;padding:14px 20px;border-bottom:1px solid #30363d;
    display:flex;align-items:center;gap:14px}
  header h1{color:#f0f6fc;font-size:16px;font-weight:700}  
  #status{font-size:11px;padding:3px 10px;border-radius:10px;background:#21262d;color:#8b949e}
  #status.live{background:#1a3a2a;color:#3fb950}
  #log{padding:12px 20px;display:flex;flex-direction:column;gap:4px;overflow-y:auto;height:calc(100vh - 53px)}
  .row{display:flex;gap:12px;padding:5px 8px;border-radius:6px;align-items:flex-start}
  .row:hover{background:#161b22}
  .ts{color:#8b949e;white-space:nowrap;min-width:90px}
  .badge{font-size:10px;font-weight:700;padding:2px 7px;border-radius:4px;flex-shrink:0;margin-top:1px}
  .info .badge{background:#1a3a2a;color:#3fb950}
  .warn .badge{background:#3d2c00;color:#e3b341}
  .alert .badge{background:#3d0000;color:#f85149;animation:blink 1s infinite}
  .msg{flex:1;color:#c9d1d9}
  .alert .msg{color:#f85149;font-weight:600}
  @keyframes blink{0%,100%{opacity:1}50%{opacity:.4}}
  #empty{padding:60px;text-align:center;color:#8b949e}
</style></head>
<body>
<header>
  <h1>🩸 PRAAN — Live Logs</h1>
  <span id="status">connecting…</span>
  <span id="count" style="margin-left:auto;color:#8b949e;font-size:12px"></span>
</header>
<div id="log"><div id="empty">No events yet — waiting for activity…</div></div>
<script>
  let last = 0;
  async function poll() {
    try {
      const r = await fetch('/activity?limit=100');
      const data = await r.json();
      const el = document.getElementById('log');
      const st = document.getElementById('status');
      st.textContent = 'live'; st.className = 'live';
      document.getElementById('count').textContent = data.length + ' events';
      if (data.length === 0) return;
      document.getElementById('empty')?.remove();
      const current = data.map(e => e.ts + e.msg).join('');
      if (current === last) return;
      last = current;
      el.innerHTML = data.map(e => {
        const ts = new Date(e.ts).toLocaleTimeString('en-IN',
          {hour:'2-digit',minute:'2-digit',second:'2-digit'});
        const icon = e.type==='alert'?'🚨':e.type==='warn'?'⚠️':'✅';
        return `<div class="row ${e.type||'info'}">
          <span class="ts">${ts}</span>
          <span class="badge">${e.type||'info'}</span>
          <span class="msg">${icon} ${e.msg}</span>
        </div>`;
      }).join('');
      el.scrollTop = el.scrollHeight;
    } catch { document.getElementById('status').textContent = 'disconnected'; }
  }
  poll();
  setInterval(poll, 3000);
</script>
</body></html>
""")


@app.get("/stats", response_model=StatsOut)
def get_stats(db: Session = Depends(get_db)):
    active_requests = db.query(TransfusionRequest).filter(
        TransfusionRequest.status.in_(["pending", "matched"])
    ).count()

    donors_notified = db.query(DonorMatch).filter(
        DonorMatch.notified_at.isnot(None)
    ).count()

    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    confirmed_today = db.query(DonorMatch).filter(
        DonorMatch.confirmed == True,
        DonorMatch.confirmed_at >= today_start,
    ).count()

    # Average hours between match creation and confirmation
    avg_seconds = db.query(
        func.avg(
            func.extract("epoch", DonorMatch.confirmed_at - DonorMatch.created_at)
        )
    ).filter(DonorMatch.confirmed == True).scalar()

    if avg_seconds:
        hours = round(avg_seconds / 3600, 1)
        avg_match_time = f"{hours}h"
    else:
        avg_match_time = "N/A"

    # critical = unconfirmed requests older than 30 min
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=30)
    critical_ids = [
        r.id for r in db.query(TransfusionRequest).filter(
            TransfusionRequest.status.in_(["pending", "matched"]),
            TransfusionRequest.created_at <= cutoff
        ).all()
        if not db.query(DonorMatch).filter(
            DonorMatch.request_id == r.id, DonorMatch.confirmed == True
        ).first()
    ]

    # patients due within 7 days
    in_7_days = date.today() + timedelta(days=7)
    patients_due = db.query(TransfusionRequest).filter(
        TransfusionRequest.predicted_date <= in_7_days,
        TransfusionRequest.status.in_(["pending", "matched"])
    ).count()

    return StatsOut(
        active_requests=active_requests,
        donors_notified=donors_notified,
        confirmed_today=confirmed_today,
        avg_match_time=avg_match_time,
        critical_cases=len(critical_ids),
        patients_due_7days=patients_due,
    )
