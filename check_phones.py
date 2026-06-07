import sys
sys.path.insert(0, 'backend')
from models import SessionLocal
from sqlalchemy import text

db = SessionLocal()

result = db.execute(text("""
    SELECT COUNT(*) as total FROM donors_v2
""")).fetchone()
print(f"Total donors_v2 rows: {result.total}")

result = db.execute(text("""
    SELECT COUNT(*) as matched
    FROM donors_v2 v2
    JOIN donors d ON d.phone = v2.contact_number
""")).fetchone()
print(f"Matching by phone with donors table: {result.matched}")

print("\nSample donors_v2 contact_numbers:")
rows = db.execute(text("SELECT contact_number FROM donors_v2 LIMIT 5")).fetchall()
for r in rows:
    print(f"  {r.contact_number}")

print("\nSample donors phones:")
rows = db.execute(text("SELECT phone FROM donors LIMIT 5")).fetchall()
for r in rows:
    print(f"  {r.phone}")

db.close()
