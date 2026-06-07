# PRAAN — Database Setup

## Prerequisites
- PostgreSQL 13+ installed and running

## Setup

```bash
# 1. Create the database
createdb praan_db

# 2. Load schema + seed data
psql praan_db < database/schema.sql
```

> The `compatibility.sql` file is already embedded inside `schema.sql`.  
> Run it separately only if you need to reload compatibility rules in isolation:
> ```bash
> psql praan_db < database/compatibility.sql
> ```

## Tables

| Table                  | Description                                      |
|------------------------|--------------------------------------------------|
| `patients`             | Thalassemia patients needing transfusions        |
| `donors`               | Registered blood donors                          |
| `transfusion_requests` | Upcoming/active transfusion needs per patient    |
| `donor_matches`        | Donor–request pairings with match scores         |
| `blood_compatibility`  | Donor→recipient blood type compatibility rules   |

## Seed Data
- 5 patients across Delhi, Mumbai, Bengaluru, Chennai
- 15 active/inactive donors (5 per city)
- 3 sample transfusion requests with varying urgency levels

## Useful Queries

```sql
-- Find compatible active donors in same city for a request
SELECT d.name, d.phone, d.blood_type, d.response_score
FROM donors d
JOIN transfusion_requests tr ON tr.id = '<request_uuid>'
JOIN patients p ON p.id = tr.patient_id
JOIN blood_compatibility bc ON bc.donor_type = d.blood_type
    AND bc.recipient_type = p.blood_type
WHERE d.city = p.city
  AND d.is_active = TRUE
ORDER BY d.response_score DESC;

-- List all pending urgent requests
SELECT p.name, p.blood_type, p.city, tr.predicted_date
FROM transfusion_requests tr
JOIN patients p ON p.id = tr.patient_id
WHERE tr.urgency = 'urgent' AND tr.status = 'pending';
```
