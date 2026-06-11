# PRAAN — Predictive Real-Time Autonomous Assisted Network

> An AI-powered blood donor matching platform for Thalassemia patients, combining predictive scoring, real-time coordination, and automated outreach to connect patients with the right donors at the right time.

---

## What is PRAAN?

Thalassemia patients require regular blood transfusions throughout their lives. Finding compatible, available donors in time is often a logistical challenge that falls on hospital staff and patients' families. PRAAN automates this end-to-end — predicting transfusion windows, scoring and ranking donors, and reaching out to the best-matched donors automatically.

**PRAAN** stands for **Predictive Real-Time Autonomous Assisted Network**.

---

## Key Features

- **Predictive Transfusion Scheduling** — Forecasts upcoming transfusion needs per patient based on historical data and urgency levels.
- **TOPSIS-Based Donor Ranking** — Ranks donors using a multi-criteria decision algorithm weighing reliability score (40%), donation recency (40%), and active status (20%).
- **Blood Type Compatibility Engine** — Enforces blood group compatibility rules between donors and recipients via a dedicated database table.
- **Automated Donor Outreach** — A bot (`praan-bot`) contacts ranked donors via SMS/email and tracks responses.
- **REST API Backend** — FastAPI-powered backend exposing endpoints for patients, donors, transfusion requests, and match management.
- **React Frontend** — Dashboard for hospital staff to view patients, active requests, and donor matches.
- **AWS-Native Deployment** — Runs on AWS App Runner (backend), Amazon RDS PostgreSQL (database), and Amazon ECR (container registry). Uses Amazon Bedrock (Nova Micro) for AI features.

---

## Demo

> 📊 [View Full Pitch Deck →](https://drive.google.com/file/d/1T30C6QSyZ7vKBP7cEa_fybMOpgSv6KRr/view?usp=sharing)

### Dashboard
![PRAAN Dashboard](docs/screenshots/dashboard.png)
*Hospital coordinator view — active requests, donor status, critical cases*

### Veeru Bot in Action

| Blood Request Flow | Donor Confirmation | Transfusion Reminder | Escalation |
|---|---|---|---|
| ![](docs/screenshots/bot-request.png) | ![](docs/screenshots/bot-donor.png) | ![](docs/screenshots/bot-reminder.png) | ![](docs/screenshots/bot-escalation.png) |
| Patient creates urgent A+ request | Donor gets match score + distance, replies YES | Predicted date reminder, patient confirms | Auto-escalation after 30 min no response |

---

## Architecture

### End-to-End Flow

```
 PATIENT          VEERU AI BOT       HYBRID RANKING        DONOR            BLOOD
SENDS REQUEST  →  (AWS Bedrock)   →  ENGINE               OUTREACH    →   DELIVERED
                                     (Proximity + TOPSIS)
```

### System Architecture

```
┌──────────────────┐     ┌──────────────────────────────────────────────┐
│  React 19        │     │               FastAPI Backend                │
│  Dashboard       │◄───►│  • SQLAlchemy ORM  • REST APIs (15+)         │
│  (Recharts,      │     │  • Auto-Escalation Engine                    │
│   Axios)         │     │  • Uvicorn ASGI Server                       │
└──────────────────┘     └──────────────────┬───────────────────────────┘
                                            │
              ┌─────────────────────────────┼──────────────────────────┐
              ▼                             ▼                          ▼
 ┌────────────────────┐      ┌──────────────────────┐    ┌─────────────────────┐
 │  AI & Intelligence │      │    PostgreSQL 13+     │    │  Bot & Communication│
 │                    │      │                       │    │                     │
 │  Amazon Bedrock    │      │  • patients           │    │  Python Telegram Bot│
 │  (Nova Micro)      │      │  • donors             │    │  (Veeru AI Agent)   │
 │                    │      │  • transfusion_       │    │                     │
 │  Multilingual NLU  │      │    requests           │    │  Conversational     │
 │  EN/HI/TE/TA       │      │  • donor_matches      │    │  State Machine      │
 │                    │      │  • blood_             │    │                     │
 │  Hybrid Ranking    │      │    compatibility      │    │  HTTPX Async        │
 │  Engine            │      │                       │    │  Requests           │
 │                    │      │  Donor & Patient      │    │                     │
 │  TOPSIS Scoring    │      │  Network              │    │  Email              │
 │                    │      │  Relationship         │    │  Notifications      │
 │  Haversine         │      │  Mapping              │    │  (SMTP/Gmail)       │
 │  Proximity         │      │  Matching Dataset     │    │                     │
 └────────────────────┘      └──────────────────────┘    └─────────────────────┘
```

### Donor Matching Pipeline

```
Blood Request
     │
     ▼
Blood Compatibility Check
     │
     ▼
Eligibility Check
     │
     ▼
Active Donor Check
     │
     ▼
Calculate Distance (Proximity Score — Haversine)
     │
     ▼
TOPSIS Suitability Score
     │
     ▼
Final Score = 60% TOPSIS + 40% Proximity
     │
     ▼
Top 3 Donors Selected  →  Primary + Backup 1 + Backup 2
     │
     ▼
Rank by Final Score  →  Ready for Outreach
```

### Auto-Escalation Tiers

```
Outreach sent → 30 min → No response → Escalate to Backup Donor 1
                60 min → No response → Escalate to Backup Donor 2
                90 min → No response → Alert Coordinator (real-time)
```

**Infrastructure:** AWS App Runner · Amazon RDS (PostgreSQL 13+) · Amazon ECR · Amazon Bedrock (Nova Micro)

---

## Repository Structure

```
PRAAN/
├── backend/               # FastAPI application (Python)
│   └── models.py          # SQLAlchemy ORM models
├── database/
│   ├── schema.sql          # Full schema + seed data
│   └── compatibility.sql  # Blood type compatibility rules
├── frontend/              # React dashboard (JavaScript)
├── praan-bot/             # Automated donor outreach bot
├── add_topsis.py          # One-time script: compute TOPSIS scores for donors
├── check_db.py            # Database health check utility
├── check_donors.py        # Donor data validation
├── debug_match.py         # Matching algorithm debugger
├── apprunner_config.json  # AWS App Runner deployment config
├── deploy_apprunner.ps1   # Deployment scripts (PowerShell)
└── deploy_rds.ps1
```

---

## Database Schema

| Table | Description |
|---|---|
| `patients` | Thalassemia patients needing transfusions |
| `donors` | Registered blood donors with scoring metadata |
| `transfusion_requests` | Upcoming and active transfusion needs per patient |
| `donor_matches` | Donor–request pairings with TOPSIS match scores |
| `blood_compatibility` | Donor → recipient blood type compatibility rules |

---

## Donor Scoring (TOPSIS)

Each donor receives a composite `topsis_score` between 0 and 1:

```
topsis_score = 0.40 × response_score  (reliability)
             + 0.40 × recency          (days since last donation, up to 365)
             + 0.20 × is_active        (1 if active, 0 otherwise)
```

To recompute scores after bulk donor imports:

```bash
python add_topsis.py
```

---

## Local Setup

### Prerequisites

- Python 3.10+
- Node.js 18+
- PostgreSQL 13+

### 1. Database

```bash
createdb praan_db
psql praan_db < database/schema.sql
```

To reload compatibility rules only:

```bash
psql praan_db < database/compatibility.sql
```

### 2. Backend

```bash
cd backend
pip install -r requirements.txt
DATABASE_URL=postgresql://user:password@localhost:5432/praan_db uvicorn app:app --reload
```

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

### 4. Bot

```bash
cd praan-bot
npm install
node index.js
```

---

## Environment Variables

| Variable | Description |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string |
| `AWS_REGION` | AWS region (e.g. `us-east-1`) |
| `BEDROCK_MODEL` | Amazon Bedrock model ID |
| `SMTP_HOST` | SMTP server for email alerts |
| `SMTP_PORT` | SMTP port (587 for TLS) |
| `SMTP_USER` | Sender email address |
| `SMTP_PASS` | App password for SMTP |
| `BLOOD_BANK_EMAIL` | Recipient email for blood bank notifications |
| `FROM_EMAIL` | From address for outbound emails |

---

## AWS Deployment

The backend is containerized and deployed via AWS App Runner.

```bash
# Build and push image to ECR
docker build -t praan-backend ./backend
docker tag praan-backend:latest <account>.dkr.ecr.us-east-1.amazonaws.com/praan-backend:latest
docker push <account>.dkr.ecr.us-east-1.amazonaws.com/praan-backend:latest

# Deploy (PowerShell)
./deploy_apprunner.ps1
```

App Runner config is in `apprunner_config.json`. The service runs on 0.25 vCPU / 0.5 GB at port `8000`.

---

## Useful Queries

```sql
-- Find compatible active donors in same city for a request
SELECT d.name, d.phone, d.blood_type, d.response_score, d.topsis_score
FROM donors d
JOIN transfusion_requests tr ON tr.id = '<request_uuid>'
JOIN patients p ON p.id = tr.patient_id
JOIN blood_compatibility bc
  ON bc.donor_type = d.blood_type AND bc.recipient_type = p.blood_type
WHERE d.city = p.city AND d.is_active = TRUE
ORDER BY d.topsis_score DESC;

-- List all pending urgent requests
SELECT p.name, p.blood_type, p.city, tr.predicted_date
FROM transfusion_requests tr
JOIN patients p ON p.id = tr.patient_id
WHERE tr.urgency = 'urgent' AND tr.status = 'pending';
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| **AI & Intelligence** | Amazon Bedrock (Nova Micro), Multilingual NLU (EN/HI/TE/TA), Hybrid Ranking Engine, TOPSIS Scoring, Haversine Proximity |
| **Bot & Communication** | Python Telegram Bot (Veeru AI Agent), Conversational State Machine, HTTPX Async Requests, Email Notifications |
| **Backend API** | FastAPI (Python), SQLAlchemy ORM, REST APIs (15+), Auto-Escalation Engine, Uvicorn ASGI Server |
| **Data Layer** | PostgreSQL 13+, Donor & Patient Network, Relationship Mapping, Matching Dataset Store |
| **Frontend & Deployment** | React 19 Dashboard, Axios API Client, Recharts Analytics, Docker Containers, AWS App Runner & Amplify |

---

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/your-feature`)
3. Commit your changes
4. Open a pull request

Please ensure database migrations are backward-compatible and new donor criteria changes come with an updated `add_topsis.py` run.

---

## License

This project is currently unlicensed. Contact the repository owner for usage permissions.

---

*Built to reduce the time between a transfusion need and a matched donor — because in thalassemia care, timing is everything.*
