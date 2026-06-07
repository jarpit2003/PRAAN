import sys
sys.path.insert(0, 'backend')
from models import SessionLocal, Donor
from sqlalchemy import text

db = SessionLocal()

print("=== All Donors (latest 10) ===")
donors = db.query(Donor).order_by(Donor.created_at.desc()).limit(10).all()
for d in donors:
    print(f"{d.name} | {d.phone} | {d.blood_type} | {d.city} | active={d.is_active} | created={str(d.created_at)[:19]}")

print("\n=== donors_v2 entries registered via bot (user_id as UUID) ===")
rows = db.execute(text("""
    SELECT user_id, blood_group, gender, contact_number, 
           donated_earlier, last_donation_date, total_score,
           bridge_status, donor_availability_score, eligibility_status
    FROM donors_v2
    WHERE eligibility_status = 'eligible'
    ORDER BY id DESC LIMIT 10
""")).fetchall()
if not rows:
    print("No eligible donors in donors_v2")
for r in rows:
    print(f"uid={r.user_id} | {r.blood_group} | {r.gender} | {r.contact_number} | total_score={r.total_score} | bridge={r.bridge_status}")

db.close()
