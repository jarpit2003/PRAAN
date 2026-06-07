"""
Run from backend/ directory:
    py -3 simulate.py
    py -3 simulate.py <patient-uuid>
"""
import sys
import os

# Ensure backend/ is on the path so local modules resolve
sys.path.insert(0, os.path.dirname(__file__))

from models import SessionLocal
from whatsapp import simulate_whatsapp_flow

db = SessionLocal()

try:
    if len(sys.argv) > 1:
        patient_id = sys.argv[1]
        simulate_whatsapp_flow(patient_id, db)
    else:
        # No UUID given — run simulation for ALL patients that have a matched request
        from models import Patient, TransfusionRequest

        patients_with_matches = (
            db.query(Patient)
            .join(TransfusionRequest, TransfusionRequest.patient_id == Patient.id)
            .filter(TransfusionRequest.status == "matched")
            .distinct()
            .all()
        )

        if not patients_with_matches:
            print("No patients with matched requests found.")
            print("Tip: POST /requests/{id}/match first to create matches.")
        else:
            for p in patients_with_matches:
                simulate_whatsapp_flow(str(p.id), db)
finally:
    db.close()
