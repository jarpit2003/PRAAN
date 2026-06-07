from __future__ import annotations
from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID
from pydantic import BaseModel


# ── Patient ──────────────────────────────────────────────

class PatientOut(BaseModel):
    id:               UUID
    name:             str
    blood_type:       str
    city:             str
    hemoglobin_level: Optional[Decimal]
    last_transfusion: Optional[date]
    thalassemia_type: Optional[str]
    created_at:       Optional[datetime]

    model_config = {"from_attributes": True}


# ── Donor ─────────────────────────────────────────────────

class DonorOut(BaseModel):
    id:                 UUID
    name:               str
    phone:              str
    blood_type:         str
    city:               str
    response_score:     Optional[Decimal]
    last_donation:      Optional[date]
    preferred_language: Optional[str]
    is_active:          bool

    model_config = {"from_attributes": True}


# ── Transfusion Request ───────────────────────────────────

class RequestCreate(BaseModel):
    patient_id:     UUID
    predicted_date: date
    urgency:        str   # urgent | normal | planned
    notes:          Optional[str] = None


class RequestOut(BaseModel):
    id:             UUID
    patient_id:     UUID
    predicted_date: date
    urgency:        str
    status:         str
    notes:          Optional[str]
    created_at:     Optional[datetime]
    patient:        Optional[PatientOut] = None

    model_config = {"from_attributes": True}


# ── Donor Match ───────────────────────────────────────────

class MatchOut(BaseModel):
    id:          UUID
    request_id:  UUID
    donor_id:    UUID
    match_score: Decimal
    confirmed:   bool
    confirmed_at: Optional[datetime]
    notified_at:  Optional[datetime]
    donor:        Optional[DonorOut] = None

    model_config = {"from_attributes": True}


# ── Prediction ──────────────────────────────────────────────

class PredictionOut(BaseModel):
    patient_id:        UUID
    patient_name:      str
    predicted_date:    date
    days_until_needed: int
    urgency:           str
    confidence:        float
    reasoning:         str


# ── Request Detail with matches ─────────────────────────

class MatchDetailOut(BaseModel):
    id:              UUID
    donor_id:        UUID
    match_score:     Decimal
    confirmed:       bool
    confirmed_at:    Optional[datetime]
    notified_at:     Optional[datetime]
    rank:            int
    donor:           Optional[DonorOut] = None
    reasons:         list[str] = []
    # Flow 2 score breakdown
    total_score:     Optional[float] = None   # 60% weight — TOPSIS from dataset
    proximity_score: Optional[float] = None   # 40% weight — Bedrock geocode + Haversine
    distance_km:     Optional[float] = None

    model_config = {"from_attributes": True}


# ── Flow 2 scored candidate (pre-save preview) ────────────

class ScoredDonorOut(BaseModel):
    rank:            int
    donor_id:        str
    name:            str
    phone:           str
    blood_type:      str
    distance_km:     float
    total_score:     float    # TOPSIS (dataset) — 60% weight
    proximity_score: float    # Bedrock geocode + Haversine — 40% weight
    final_score:     float    # 0.60 * total_score + 0.40 * proximity_score
    days_since_donation: Optional[int] = None


class RequestDetailOut(BaseModel):
    id:             UUID
    patient_id:     UUID
    predicted_date: date
    urgency:        str
    status:         str
    notes:          Optional[str]
    raised_by:      Optional[str]
    created_at:     Optional[datetime]
    patient:        Optional[PatientOut] = None
    matches:        list[MatchDetailOut] = []

    model_config = {"from_attributes": True}


# ── Critical case ─────────────────────────────────────────

class CriticalCaseOut(BaseModel):
    id:               str
    patient:          str
    blood_type:       str
    city:             str
    urgency:          str
    status:           str
    waiting_minutes:  int
    reason:           str
    current_stage:    str
    raised_by:        str


# ── Stats ─────────────────────────────────────────────────

class StatsOut(BaseModel):
    active_requests:    int
    donors_notified:    int
    confirmed_today:    int
    avg_match_time:     str
    critical_cases:     int
    patients_due_7days: int
