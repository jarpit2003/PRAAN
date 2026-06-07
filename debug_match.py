import sys
sys.path.insert(0, 'backend')
from models import SessionLocal, Patient, Donor, TransfusionRequest, DonorMatch
from matcher import donors_v2_match, sql_fallback_donors, match_donors_for_patient
from sqlalchemy import text

db = SessionLocal()

# Show latest request
req = db.query(TransfusionRequest).order_by(TransfusionRequest.created_at.desc()).first()
patient = db.query(Patient).filter(Patient.id == req.patient_id).first()
print(f"Latest request: {str(req.id)[:8]} | Patient: {patient.name} | Blood: {patient.blood_type} | City: {patient.city}")

# Test donors_v2_match directly
print("\n--- Testing donors_v2_match ---")
patient.location = patient.city
try:
    v2_results = donors_v2_match(patient, db, limit=5)
    print(f"donors_v2_match returned: {len(v2_results)} donors")
    for d in v2_results:
        print(f"  {d['name']} | {d['blood_type']} | score={d['match_score']} | id={d['donor_id']}")
except Exception as e:
    print(f"donors_v2_match ERROR: {e}")

# Test sql_fallback directly
print("\n--- Testing sql_fallback_donors ---")
try:
    fb_results = sql_fallback_donors(patient, db, limit=5)
    print(f"sql_fallback returned: {len(fb_results)} donors")
    for d in fb_results:
        print(f"  {d['name']} | {d['blood_type']} | {d['city']} | score={d['match_score']} | id={d['donor_id']}")
except Exception as e:
    print(f"sql_fallback ERROR: {e}")

# Test full match pipeline
print("\n--- Testing match_donors_for_patient ---")
try:
    results, source = match_donors_for_patient(patient, db, limit=5)
    print(f"Source: {source} | Found: {len(results)} donors")
    for d in results:
        print(f"  {d['name']} | {d['blood_type']} | score={d['match_score']} | id={d['donor_id']}")
except Exception as e:
    print(f"match_donors_for_patient ERROR: {e}")

# Check donors table for compatible donors in same city
print(f"\n--- Compatible active donors in {patient.city} for {patient.blood_type} ---")
rows = db.execute(text("""
    SELECT d.name, d.blood_type, d.city, d.is_active, d.response_score
    FROM donors d
    JOIN blood_compatibility bc ON bc.donor_type = d.blood_type AND bc.recipient_type = :bt
    WHERE d.is_active = true
    ORDER BY d.response_score DESC
"""), {"bt": patient.blood_type}).fetchall()
print(f"Total compatible active donors (any city): {len(rows)}")
for r in rows:
    print(f"  {r.name} | {r.blood_type} | {r.city} | active={r.is_active} | score={r.response_score}")

db.close()
