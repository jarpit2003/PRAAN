import sys
sys.path.insert(0, 'backend')
from models import SessionLocal, Donor, TransfusionRequest, DonorMatch, Patient

db = SessionLocal()

name = ""

if name:
    patient = db.query(Patient).filter(Patient.name.ilike(f"%{name}%")).first()
    if not patient:
        print(f"No patient found with name '{name}'")
        db.close()
        exit()
    req = (
        db.query(TransfusionRequest)
        .filter(TransfusionRequest.patient_id == patient.id)
        .order_by(TransfusionRequest.created_at.desc())
        .first()
    )
else:
    req = db.query(TransfusionRequest).order_by(TransfusionRequest.created_at.desc()).first()
    patient = db.query(Patient).filter(Patient.id == req.patient_id).first() if req else None

if not req:
    print("No requests found.")
    db.close()
    exit()

print(f"\n=== Request ===")
print(f"Patient : {patient.name} | Blood: {patient.blood_type} | City: {patient.city}")
print(f"Request : {str(req.id)[:8]} | {req.urgency} | {req.status} | {req.predicted_date}")

print(f"\n=== Top 3 Matched Donors ===")
matches = (
    db.query(DonorMatch)
    .filter(DonorMatch.request_id == req.id)
    .order_by(DonorMatch.match_score.desc())
    .limit(3).all()
)
if not matches:
    print("No donor matches found. Run a new request via bot after restarting backend.")
for i, m in enumerate(matches, 1):
    donor = db.query(Donor).filter(Donor.id == m.donor_id).first()
    name  = donor.name if donor else "Unknown"
    phone = donor.phone if donor else "-"
    bt    = donor.blood_type if donor else "-"
    city  = donor.city if donor else "-"
    status = "✅ Confirmed" if m.confirmed else "⏳ Pending"
    print(f"#{i} {name} | {bt} | {city} | {phone} | score={m.match_score} | {status}")

db.close()

# List all patients
print("\n=== All Patients in DB ===")
db2 = SessionLocal()
patients = db2.query(Patient).order_by(Patient.created_at.desc()).all()
for p in patients:
    print(f"{p.name} | {p.blood_type} | {p.city}")
db2.close()
