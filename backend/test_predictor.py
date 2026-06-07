from datetime import date, timedelta
from unittest.mock import patch

import pytest
from predictor import predict_next_transfusion


TODAY = date(2025, 6, 10)   # fixed reference date for all tests


def run(patient):
    """Patch date.today() to a fixed value so tests never drift."""
    with patch("predictor.date") as mock_date:
        mock_date.today.return_value = TODAY
        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
        return predict_next_transfusion(patient)


# ── Test 1: HB estimate is sooner than cycle estimate ────
def test_hb_drives_prediction_when_sooner():
    # last_hb = 8.0  →  days_hb = ((8.0 - 7.0) / 0.5) * 7 = 14
    # last_transfusion = 4 days ago, cycle = 21  →  days_cycle = 17
    # sooner = 14 (HB estimate)
    result = run({
        "last_hb": 8.0,
        "last_transfusion": TODAY - timedelta(days=4),
        "thal_type": "beta-major",
    })
    assert result["days_until_needed"] == 14
    assert result["predicted_date"] == TODAY + timedelta(days=14)
    assert result["urgency"] == "planned"
    assert "hemoglobin" in result["reasoning"]
    assert 0.0 <= result["confidence"] <= 1.0


# ── Test 2: cycle estimate is sooner than HB estimate ────
def test_cycle_drives_prediction_when_sooner():
    # last_hb = 10.0  →  days_hb = ((10.0 - 7.0) / 0.5) * 7 = 42
    # last_transfusion = 20 days ago, cycle = 21  →  days_cycle = 1
    # sooner = 1 (cycle estimate) → urgency = urgent
    result = run({
        "last_hb": 10.0,
        "last_transfusion": TODAY - timedelta(days=20),
        "thal_type": "beta-major",
    })
    assert result["days_until_needed"] == 1
    assert result["predicted_date"] == TODAY + timedelta(days=1)
    assert result["urgency"] == "urgent"
    assert "cycle" in result["reasoning"]


# ── Test 3: HB already below threshold → predict today ───
def test_hb_below_threshold_is_urgent():
    result = run({
        "last_hb": 6.5,
        "last_transfusion": TODAY - timedelta(days=10),
        "thal_type": "alpha",
    })
    assert result["days_until_needed"] == 0
    assert result["predicted_date"] == TODAY
    assert result["urgency"] == "urgent"


# ── Test 4: determinism — same inputs always same output ──
def test_deterministic():
    patient = {
        "last_hb": 8.5,
        "last_transfusion": TODAY - timedelta(days=7),
        "thal_type": "beta-intermedia",
    }
    r1 = run(patient)
    r2 = run(patient)
    assert r1 == r2
