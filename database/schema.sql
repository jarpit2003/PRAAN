-- PRAAN: Blood Donor-Patient Matching System
-- Run: psql praan_db < schema.sql

-- Enable UUID generation
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ─────────────────────────────────────────
-- TABLES
-- ─────────────────────────────────────────

CREATE TABLE patients (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name                VARCHAR(100) NOT NULL,
    blood_type          VARCHAR(3)   NOT NULL CHECK (blood_type IN ('O+','O-','A+','A-','B+','B-','AB+','AB-')),
    city                VARCHAR(50)  NOT NULL,
    hemoglobin_level    NUMERIC(4,1),                -- g/dL
    last_transfusion    DATE,
    thalassemia_type    VARCHAR(30)  CHECK (thalassemia_type IN ('alpha','beta','beta-intermedia','beta-major')),
    created_at          TIMESTAMPTZ  DEFAULT now()
);

CREATE TABLE donors (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name                VARCHAR(100) NOT NULL,
    phone               VARCHAR(15)  NOT NULL UNIQUE,
    blood_type          VARCHAR(3)   NOT NULL CHECK (blood_type IN ('O+','O-','A+','A-','B+','B-','AB+','AB-')),
    city                VARCHAR(50)  NOT NULL,
    response_score      NUMERIC(3,1) DEFAULT 5.0 CHECK (response_score BETWEEN 0 AND 10),
    last_donation       DATE,
    preferred_language  VARCHAR(2)   DEFAULT 'en' CHECK (preferred_language IN ('en','hi','te','ta')),
    is_active           BOOLEAN      DEFAULT TRUE,
    created_at          TIMESTAMPTZ  DEFAULT now()
);

CREATE TABLE transfusion_requests (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id          UUID         NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    predicted_date      DATE         NOT NULL,
    urgency             VARCHAR(10)  NOT NULL CHECK (urgency IN ('urgent','normal','planned')),
    status              VARCHAR(10)  NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','matched','fulfilled')),
    notes               TEXT,
    created_at          TIMESTAMPTZ  DEFAULT now()
);

CREATE TABLE donor_matches (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id          UUID         NOT NULL REFERENCES transfusion_requests(id) ON DELETE CASCADE,
    donor_id            UUID         NOT NULL REFERENCES donors(id) ON DELETE CASCADE,
    match_score         NUMERIC(5,2) NOT NULL,       -- 0–100
    confirmed           BOOLEAN      DEFAULT FALSE,
    confirmed_at        TIMESTAMPTZ,
    notified_at         TIMESTAMPTZ,
    created_at          TIMESTAMPTZ  DEFAULT now(),
    UNIQUE (request_id, donor_id)
);

-- ─────────────────────────────────────────
-- BLOOD COMPATIBILITY
-- ─────────────────────────────────────────

CREATE TABLE blood_compatibility (
    donor_type          VARCHAR(3) NOT NULL,
    recipient_type      VARCHAR(3) NOT NULL,
    PRIMARY KEY (donor_type, recipient_type)
);

INSERT INTO blood_compatibility (donor_type, recipient_type) VALUES
('O-', 'O-'), ('O-', 'O+'), ('O-', 'A-'), ('O-', 'A+'),
('O-', 'B-'), ('O-', 'B+'), ('O-', 'AB-'), ('O-', 'AB+'),
('O+', 'O+'), ('O+', 'A+'), ('O+', 'B+'), ('O+', 'AB+'),
('A-', 'A-'), ('A-', 'A+'), ('A-', 'AB-'), ('A-', 'AB+'),
('A+', 'A+'), ('A+', 'AB+'),
('B-', 'B-'), ('B-', 'B+'), ('B-', 'AB-'), ('B-', 'AB+'),
('B+', 'B+'), ('B+', 'AB+'),
('AB-', 'AB-'), ('AB-', 'AB+'),
('AB+', 'AB+');

-- ─────────────────────────────────────────
-- SEED: 5 PATIENTS
-- ─────────────────────────────────────────

INSERT INTO patients (name, blood_type, city, hemoglobin_level, last_transfusion, thalassemia_type) VALUES
('Aarav Sharma',     'B+',  'Delhi',     6.2, '2025-05-15', 'beta-major'),
('Priya Nair',       'O+',  'Mumbai',    5.8, '2025-04-28', 'beta-major'),
('Ravi Kumar',       'A+',  'Bengaluru', 7.1, '2025-05-01', 'beta-intermedia'),
('Meena Iyer',       'AB+', 'Chennai',   6.5, '2025-05-10', 'beta-major'),
('Arjun Patel',      'B-',  'Mumbai',    5.5, '2025-04-20', 'alpha');

-- ─────────────────────────────────────────
-- SEED: 15 DONORS
-- ─────────────────────────────────────────

INSERT INTO donors (name, phone, blood_type, city, response_score, last_donation, preferred_language, is_active) VALUES
-- Bengaluru (5)
('Suresh Reddy',       '+919845001001', 'B+',  'Bengaluru', 8.5, '2025-02-10', 'te', TRUE),
('Kavitha Rao',        '+919845001002', 'O+',  'Bengaluru', 9.0, '2025-01-22', 'te', TRUE),
('Manjunath S',        '+919845001003', 'A+',  'Bengaluru', 7.2, '2025-03-05', 'en', TRUE),
('Divya Menon',        '+919845001004', 'O-',  'Bengaluru', 9.5, '2024-12-18', 'en', TRUE),
('Harish Gowda',       '+919845001005', 'AB+', 'Bengaluru', 6.8, '2025-04-01', 'te', FALSE),
-- Mumbai (5)
('Rohit Desai',        '+919820002001', 'O+',  'Mumbai',    8.0, '2025-03-15', 'hi', TRUE),
('Sunita Joshi',       '+919820002002', 'A-',  'Mumbai',    7.5, '2025-02-28', 'hi', TRUE),
('Deepak Kulkarni',    '+919820002003', 'B+',  'Mumbai',    8.8, '2025-01-10', 'en', TRUE),
('Pooja Mehta',        '+919820002004', 'O-',  'Mumbai',    9.2, '2024-11-30', 'hi', TRUE),
('Amit Patil',         '+919820002005', 'AB-', 'Mumbai',    6.5, '2025-04-20', 'hi', FALSE),
-- Delhi (5)
('Vikram Singh',       '+919711003001', 'B+',  'Delhi',     7.9, '2025-03-22', 'hi', TRUE),
('Neha Gupta',         '+919711003002', 'A+',  'Delhi',     8.3, '2025-02-14', 'hi', TRUE),
('Rajesh Yadav',       '+919711003003', 'O+',  'Delhi',     7.0, '2025-01-05', 'hi', TRUE),
('Anita Chauhan',      '+919711003004', 'B-',  'Delhi',     9.1, '2025-04-08', 'en', TRUE),
('Sanjay Verma',       '+919711003005', 'O-',  'Delhi',     8.6, '2024-12-25', 'hi', TRUE);

-- ─────────────────────────────────────────
-- SEED: TRANSFUSION REQUESTS
-- ─────────────────────────────────────────

INSERT INTO transfusion_requests (patient_id, predicted_date, urgency, status, notes)
SELECT id, CURRENT_DATE + 3,  'urgent',  'pending', 'Hemoglobin critically low'    FROM patients WHERE name = 'Aarav Sharma'
UNION ALL
SELECT id, CURRENT_DATE + 7,  'normal',  'pending', 'Routine monthly transfusion'  FROM patients WHERE name = 'Priya Nair'
UNION ALL
SELECT id, CURRENT_DATE + 14, 'planned', 'pending', 'Scheduled quarterly session'  FROM patients WHERE name = 'Ravi Kumar';
