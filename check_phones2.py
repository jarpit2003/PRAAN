import sys
sys.path.insert(0, 'backend')
from models import SessionLocal
from sqlalchemy import text

db = SessionLocal()

# Try normalizing scientific notation to match +91XXXXXXXXXX
result = db.execute(text("""
    SELECT COUNT(*) as matched
    FROM donors_v2 v2
    JOIN donors d ON d.phone = '+' || LPAD(REGEXP_REPLACE(CAST(CAST(v2.contact_number AS NUMERIC) AS BIGINT)::TEXT, '[^0-9]', '', 'g'), 12, '0')
""")).fetchone()
print(f"Match after normalization attempt 1: {result.matched}")

# Show what normalized phone looks like
rows = db.execute(text("""
    SELECT contact_number,
           CAST(CAST(contact_number AS NUMERIC) AS BIGINT) as as_int
    FROM donors_v2 LIMIT 5
""")).fetchall()
print("\nScientific -> Integer:")
for r in rows:
    print(f"  {r.contact_number} -> {r.as_int}")

db.close()
