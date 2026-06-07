from datetime import date, timedelta

HB_THRESHOLD      = 7.0   # g/dL — transfusion needed below this
HB_DROP_RATE      = 0.5   # g/dL per week
CYCLE_DAYS = {
    "beta-major":      21,
    "beta-intermedia": 21,
    "beta":            21,
    "alpha":           28,
}
DEFAULT_CYCLE = 21


def _urgency(days: int) -> str:
    if days <= 2:
        return "urgent"
    if days <= 5:
        return "normal"
    return "planned"


def _confidence(last_hb: float, days_hb: int, days_cycle: int) -> float:
    """
    Higher confidence when both estimates agree and HB is known.
    Penalised when HB is borderline or estimates diverge widely.
    """
    base = 0.85 if last_hb is not None else 0.50
    divergence = abs(days_hb - days_cycle)
    penalty = min(divergence / 30, 0.30)   # cap penalty at 0.30
    return round(max(0.0, min(1.0, base - penalty)), 2)


def predict_next_transfusion(patient: dict) -> dict:
    """
    Predict when a thalassemia patient will next need a transfusion.

    Required keys:
        last_hb          (float | None)  – most recent hemoglobin in g/dL
        last_transfusion (date  | None)  – date of last transfusion
        thal_type        (str   | None)  – thalassemia type string

    Returns a dict with: predicted_date, days_until_needed,
                         urgency, confidence, reasoning.
    """
    today        = date.today()
    last_hb      = patient.get("last_hb")
    last_tx      = patient.get("last_transfusion")
    thal_type    = (patient.get("thal_type") or "").lower()
    cycle        = CYCLE_DAYS.get(thal_type, DEFAULT_CYCLE)

    # ── Estimate 1: hemoglobin drop rate ─────────────────
    if last_hb is not None and last_hb > HB_THRESHOLD:
        days_hb = int(((last_hb - HB_THRESHOLD) / HB_DROP_RATE) * 7)
    elif last_hb is not None:
        days_hb = 0   # already below threshold → needed now
    else:
        days_hb = cycle   # no HB data, fall back to cycle

    # ── Estimate 2: average transfusion cycle ────────────
    if last_tx is not None:
        days_since_last = (today - last_tx).days
        days_cycle = max(0, cycle - days_since_last)
    else:
        days_cycle = cycle

    # ── Take the sooner estimate ─────────────────────────
    days_until = min(days_hb, days_cycle)
    predicted_date = today + timedelta(days=days_until)
    urgency = _urgency(days_until)

    # ── Confidence ───────────────────────────────────────
    confidence = _confidence(last_hb, days_hb, days_cycle)

    # ── Reasoning ────────────────────────────────────────
    if days_hb <= days_cycle:
        driver = f"hemoglobin ({last_hb} g/dL) is projected to reach 7.0 g/dL in {days_hb} day(s)"
    else:
        driver = f"average {cycle}-day transfusion cycle since last transfusion ({last_tx}) expires in {days_cycle} day(s)"
    reasoning = f"Transfusion needed in {days_until} day(s): {driver}."

    return {
        "predicted_date":   predicted_date,
        "days_until_needed": days_until,
        "urgency":          urgency,
        "confidence":       confidence,
        "reasoning":        reasoning,
    }
