import sys
sys.path.insert(0, 'backend')
from models import SessionLocal, Donor
from sqlalchemy import text

db = SessionLocal()

# Add topsis_score column
db.execute(text("""
    ALTER TABLE donors ADD COLUMN IF NOT EXISTS topsis_score NUMERIC(6,4) DEFAULT 0.5
"""))
db.commit()
print("Column added.")

# Compute TOPSIS score for existing donors using:
# criteria: response_score (40%), recency (40%), is_active (20%)
from datetime import date

donors = db.query(Donor).all()

# Normalize each criterion to 0-1
max_rs = max((float(d.response_score or 5) for d in donors), default=10)

for d in donors:
    rs       = float(d.response_score or 5) / max_rs          # reliability 0-1
    days     = (date.today() - d.last_donation).days if d.last_donation else 0
    recency  = min(days, 365) / 365.0                          # more days = more eligible
    active   = 1.0 if d.is_active else 0.0

    topsis = round(0.40 * rs + 0.40 * recency + 0.20 * active, 4)

    db.execute(text(
        "UPDATE donors SET topsis_score = :score WHERE id = :id"
    ), {"score": topsis, "id": str(d.id)})
    print(f"{d.name} | rs={rs:.2f} recency={recency:.2f} active={active} => topsis={topsis}")

db.commit()
print("\nDone. All donors updated with topsis_score.")
db.close()
