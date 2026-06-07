"""
ivr.py — IVR fallback for patients without smartphones.

For demo: POST /ivr/incoming  { phone: "+91...", keypress: "1" or "2" }

Production: swap _simulate_ivr_response() for real Exotel TwiML XML.
"""
import os
import uuid
from datetime import date, timedelta, datetime, timezone

from whatsapp import _log, ACTIVITY_FEED

IVR_WELCOME = (
    "Welcome to PRAAN Blood Warriors. "
    "Press 1 to request blood urgently. "
    "Press 2 to check your request status. "
    "Press 9 to repeat this message."
)

IVR_CONFIRMED = (
    "Your urgent blood request has been registered. "
    "We are finding donors now. You will receive a call back within one hour. "
    "Thank you."
)

IVR_STATUS_FOUND   = "Your latest request status is {status}. Urgency level: {urgency}."
IVR_STATUS_NONE    = "We could not find any request for your number. Please contact our helpline."
IVR_UNKNOWN        = "Sorry, we did not understand your input. Please call again."


def handle_ivr_call(phone: str, keypress: str, db) -> dict:
    """
    Process an IVR keypress for a given caller phone number.
    Returns { "response_text": str, "action": str, "request_id": str|None }
    """
    from models import Patient, TransfusionRequest, DonorMatch
    from matcher import match_donors_for_patient

    keypress = str(keypress).strip()

    if keypress == "9":
        return {"response_text": IVR_WELCOME, "action": "repeat", "request_id": None}

    if keypress == "1":
        # Find or auto-create patient from phone
        patient = _find_or_create_patient_by_phone(phone, db)
        req_id  = _create_urgent_request(patient, phone, db)
        _log(f"📞 IVR: Patient {patient.name} raised URGENT request via IVR call ({phone})", "info")
        return {
            "response_text": IVR_CONFIRMED,
            "action":        "request_created",
            "request_id":    str(req_id),
        }

    if keypress == "2":
        patient = _find_or_create_patient_by_phone(phone, db)
        req = (db.query(TransfusionRequest)
               .filter(TransfusionRequest.patient_id == patient.id)
               .order_by(TransfusionRequest.created_at.desc()).first())
        if req:
            text = IVR_STATUS_FOUND.format(status=req.status, urgency=req.urgency)
            return {"response_text": text, "action": "status_read", "request_id": str(req.id)}
        return {"response_text": IVR_STATUS_NONE, "action": "not_found", "request_id": None}

    return {"response_text": IVR_UNKNOWN, "action": "unknown", "request_id": None}


def _find_or_create_patient_by_phone(phone: str, db) -> object:
    """Return existing patient linked to this phone, or create a placeholder."""
    from models import Patient, Donor
    # Check donor table first (donors have phones stored)
    donor = db.query(Donor).filter(Donor.phone == phone).first()
    if donor:
        # Donors calling for themselves — unusual but handle gracefully
        # Try to find a patient with same city/blood_type as placeholder
        patient = db.query(Patient).filter(Patient.city == donor.city).first()
        if patient:
            return patient

    # Create a placeholder patient for this IVR caller
    existing = db.query(Patient).filter(Patient.city == "Unknown").first()
    if existing:
        return existing

    new_p = Patient(
        id               = uuid.uuid4(),
        name             = f"IVR Caller {phone[-4:]}",
        blood_type       = "O+",           # default until verified
        city             = "Unknown",
        thalassemia_type = "beta-major",
    )
    db.add(new_p)
    db.commit()
    db.refresh(new_p)
    _log(f"New IVR patient placeholder created for {phone}", "info")
    return new_p


def _create_urgent_request(patient, phone: str, db) -> uuid.UUID:
    """Create an urgent TransfusionRequest and trigger matching."""
    from models import TransfusionRequest, DonorMatch, Donor
    from matcher import match_donors_for_patient
    from whatsapp import send_donation_request

    req = TransfusionRequest(
        id             = uuid.uuid4(),
        patient_id     = patient.id,
        predicted_date = date.today() + timedelta(days=1),
        urgency        = "urgent",
        status         = "pending",
        notes          = f"Raised via IVR by {phone}",
        raised_by      = "ivr",
    )
    db.add(req)
    db.commit()
    db.refresh(req)

    # Trigger matching
    scored_donors, _ = match_donors_for_patient(patient, db, limit=5)
    now = datetime.now(timezone.utc)
    for entry in scored_donors[:3]:
        from uuid import UUID
        donor_uuid = UUID(entry["donor_id"])
        db.add(DonorMatch(
            request_id  = req.id,
            donor_id    = donor_uuid,
            match_score = round(entry["match_score"], 2),
            notified_at = now,
        ))
        donor = db.query(Donor).filter(Donor.id == donor_uuid).first()
        if donor:
            send_donation_request(
                {"name": donor.name, "phone": donor.phone,
                 "language": donor.preferred_language, "blood_type": donor.blood_type},
                {"blood_type": patient.blood_type},
                str(req.id),
            )

    req.status = "matched"
    db.commit()
    _log(f"3 donors auto-notified for IVR request from {phone}", "info")
    return req.id


def simulate_ivr(phone: str, keypress: str = "1") -> None:
    """Console demo — no DB needed."""
    print(f"\n{'='*55}")
    print(f"  PRAAN IVR Simulation")
    print(f"  Caller : {phone}  |  Keypress : {keypress}")
    print(f"{'='*55}")
    print(f"  AUTO-VOICE: {IVR_WELCOME}\n")
    if keypress == "1":
        print(f"  [Caller pressed 1 — Request Blood Urgently]")
        print(f"  AUTO-VOICE: {IVR_CONFIRMED}")
        print(f"  SYSTEM: Creating urgent request + notifying donors...")
    elif keypress == "2":
        print(f"  [Caller pressed 2 — Check Status]")
        print(f"  AUTO-VOICE: {IVR_STATUS_FOUND.format(status='matched', urgency='urgent')}")
    print(f"{'='*55}\n")
