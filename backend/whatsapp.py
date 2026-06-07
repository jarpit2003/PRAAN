import os
from datetime import datetime, timezone, timedelta
from collections import deque

from dotenv import load_dotenv

load_dotenv()

TWILIO_SID     = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_TOKEN   = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_WA_FROM = "whatsapp:+14155238886"

# ── Conversation memory (in-process, hackathon-safe) ──────
# { phone: { "state": str, "lang": str, "data": dict,
#            "history": deque(maxlen=5), "last_seen": datetime } }
_SESSIONS: dict[str, dict] = {}

# Activity feed for coordinator dashboard
# [ { "ts": datetime, "msg": str, "type": "info"|"warn"|"alert" } ]
ACTIVITY_FEED: list[dict] = []

def _log(msg: str, kind: str = "info"):
    ACTIVITY_FEED.append({"ts": datetime.now(timezone.utc), "msg": msg, "type": kind})
    if len(ACTIVITY_FEED) > 200:
        ACTIVITY_FEED.pop(0)

# ── Language detection ────────────────────────────────────
_HINDI_CHARS  = set("अआइईउऊएऐओऔकखगघचछजझटठडढणतथदधनपफबभमयरलवशषसह")
_TELUGU_CHARS = set("అఆఇఈఉఊఋఌఎఏఐఒఓఔకఖగఘఙచఛజఝఞటఠడఢణతథదధనపఫబభమయరఱలళవశషసహ")
_TAMIL_CHARS  = set("அஆஇஈஉஊஎஏஐஒஓஔகஙசஞடணதநபமயரலவழளறனஜஷஸஹ")

def _detect_lang(text: str) -> str:
    chars = set(text)
    if chars & _HINDI_CHARS:  return "hi"
    if chars & _TELUGU_CHARS: return "te"
    if chars & _TAMIL_CHARS:  return "ta"
    return "en"

# ── Multilingual strings ──────────────────────────────────
_T = {
    "welcome": {
        "en": ("Hi! Welcome to PRAAN Blood Warriors 🩸\nWhat do you need?\n"
               "1. Request blood urgently\n2. Check my request status\n3. Register as a donor\n"
               "Reply with 1, 2, or 3."),
        "hi": ("नमस्ते! PRAAN Blood Warriors में आपका स्वागत है 🩸\nआपको क्या चाहिए?\n"
               "1. तुरंत रक्त की ज़रूरत है\n2. मेरी रिक्वेस्ट की स्थिति देखें\n3. डोनर के रूप में रजिस्टर करें\n"
               "1, 2 या 3 लिखें।"),
        "te": ("హలో! PRAAN Blood Warriors కి స్వాగతం 🩸\nమీకు ఏమి కావాలి?\n"
               "1. అత్యవసరంగా రక్తం అవసరం\n2. నా అభ్యర్థన స్థితి తనిఖీ చేయండి\n3. దాత గా నమోదు చేయండి\n"
               "1, 2 లేదా 3 అని reply చేయండి."),
        "ta": ("வணக்கம்! PRAAN Blood Warriors-க்கு வரவேற்கிறோம் 🩸\nஉங்களுக்கு என்ன தேவை?\n"
               "1. அவசரமாக இரத்தம் தேவை\n2. என் கோரிக்கை நிலை பார்க்க\n3. தானியாளராக பதிவு செய்ய\n"
               "1, 2 அல்லது 3 என்று பதில் அனுப்பவும்."),
    },
    "ask_phone": {
        "en": "Please share your registered phone number (with country code, e.g. +919XXXXXXXXX).",
        "hi": "कृपया अपना रजिस्टर्ड फोन नंबर शेयर करें (देश कोड के साथ, जैसे +919XXXXXXXXX)।",
        "te": "దయచేసి మీ నమోదిత ఫోన్ నంబర్ పంచుకోండి (+919XXXXXXXXX వంటిది).",
        "ta": "உங்கள் பதிவு செய்யப்பட்ட தொலைபேசி எண்ணை பகிரவும் (+919XXXXXXXXX போன்று).",
    },
    "ask_urgency": {
        "en": "How urgent is this?\nReply URGENT or NORMAL.",
        "hi": "यह कितना ज़रूरी है?\nURGENT या NORMAL लिखें।",
        "te": "ఇది ఎంత అత్యవసరం?\nURGENT లేదా NORMAL అని reply చేయండి.",
        "ta": "இது எவ்வளவு அவசரம்?\nURGENT அல்லது NORMAL என்று பதில் அனுப்பவும்.",
    },
    "request_created": {
        "en": "✅ Request received! We are finding donors now. You will get an update within 1 hour. - PRAAN",
        "hi": "✅ रिक्वेस्ट मिल गई! हम अभी डोनर ढूंढ रहे हैं। 1 घंटे में अपडेट मिलेगा। - PRAAN",
        "te": "✅ అభ్యర్థన అందింది! మేము ఇప్పుడు దాతలను వెతుకుతున్నాము. 1 గంటలో అప్డేట్ వస్తుంది. - PRAAN",
        "ta": "✅ கோரிக்கை பெறப்பட்டது! நாங்கள் இப்போது தானியாளர்களை தேடுகிறோம். 1 மணி நேரத்தில் புதுப்பிப்பு கிடைக்கும். - PRAAN",
    },
    "not_registered": {
        "en": "You're not registered yet. Let's create your profile.\nWhat is your full name?",
        "hi": "आप अभी रजिस्टर्ड नहीं हैं। आपकी प्रोफ़ाइल बनाते हैं।\nआपका पूरा नाम क्या है?",
        "te": "మీరు ఇంకా నమోదు కాలేదు. మీ ప్రొఫైల్ సృష్టిద్దాం.\nమీ పూర్తి పేరు ఏమిటి?",
        "ta": "நீங்கள் இன்னும் பதிவு செய்யவில்லை. உங்கள் சுயவிவரம் உருவாக்குவோம்.\nஉங்கள் முழு பெயர் என்ன?",
    },
    "ask_blood_type": {
        "en": "What is your blood type? (e.g. O+, B-, AB+)",
        "hi": "आपका ब्लड ग्रुप क्या है? (जैसे O+, B-, AB+)",
        "te": "మీ రక్త సమూహం ఏమిటి? (ఉదా: O+, B-, AB+)",
        "ta": "உங்கள் இரத்த வகை என்ன? (எ.கா. O+, B-, AB+)",
    },
    "ask_city": {
        "en": "Which city are you in?",
        "hi": "आप किस शहर में हैं?",
        "te": "మీరు ఏ నగరంలో ఉన్నారు?",
        "ta": "நீங்கள் எந்த நகரத்தில் இருக்கிறீர்கள்?",
    },
    "active_request": {
        "en": "Your previous request is still active. Status: {status}. Do you want to raise a new one? Reply YES or NO.",
        "hi": "आपकी पिछली रिक्वेस्ट अभी भी सक्रिय है। स्थिति: {status}। क्या आप नई रिक्वेस्ट करना चाहते हैं? YES या NO लिखें।",
        "te": "మీ మునుపటి అభ్యర్థన ఇంకా చురుగ్గా ఉంది. స్థితి: {status}। కొత్తది చేయాలా? YES లేదా NO అని reply చేయండి.",
        "ta": "உங்கள் முந்தைய கோரிக்கை இன்னும் செயலில் உள்ளது. நிலை: {status}. புதியதை உருவாக்க விரும்புகிறீர்களா? YES அல்லது NO என்று பதில் அனுப்பவும்.",
    },
    "donor_reactivated": {
        "en": "✅ Great! We've reactivated your match. The care team will contact you shortly. - PRAAN",
        "hi": "✅ बढ़िया! आपका मैच फिर से सक्रिय हो गया है। टीम जल्द संपर्क करेगी। - PRAAN",
        "te": "✅ చాలా మంచిది! మీ మ్యాచ్ మళ్ళీ సక్రియమైంది. బృందం త్వరలో సంప్రదిస్తుంది. - PRAAN",
        "ta": "✅ அருமை! உங்கள் பொருத்தம் மீண்டும் செயல்படுத்தப்பட்டது. குழு விரைவில் தொடர்பு கொள்ளும். - PRAAN",
    },
    "status_reply": {
        "en": "Your latest request status: {status} (urgency: {urgency}, predicted: {date}). - PRAAN",
        "hi": "आपकी ताज़ा रिक्वेस्ट की स्थिति: {status} (ज़रूरत: {urgency}, तारीख: {date})। - PRAAN",
        "te": "మీ తాజా అభ్యర్థన స్థితి: {status} (అత్యవసరత: {urgency}, తేదీ: {date}). - PRAAN",
        "ta": "உங்கள் சமீபத்திய கோரிக்கையின் நிலை: {status} (அவசரம்: {urgency}, தேதி: {date}). - PRAAN",
    },
    "register_donor_ask": {
        "en": "To register as a donor, please share your full name.",
        "hi": "डोनर के रूप में रजिस्टर करने के लिए, कृपया अपना पूरा नाम बताएं।",
        "te": "దాతగా నమోదు చేయడానికి, దయచేసి మీ పూర్తి పేరు చెప్పండి.",
        "ta": "தானியாளராக பதிவு செய்ய, உங்கள் முழு பெயரை தெரிவிக்கவும்.",
    },
    "donor_registered": {
        "en": "🎉 You're registered as a donor! Thank you for joining PRAAN Blood Warriors. - PRAAN",
        "hi": "🎉 आप डोनर के रूप में रजिस्टर हो गए! PRAAN Blood Warriors में शामिल होने के लिए धन्यवाद। - PRAAN",
        "te": "🎉 మీరు దాతగా నమోదు అయ్యారు! PRAAN Blood Warriors లో చేరినందుకు ధన్యవాదాలు. - PRAAN",
        "ta": "🎉 நீங்கள் தானியாளராக பதிவு செய்யப்பட்டீர்கள்! PRAAN Blood Warriors-ல் சேர்ந்தமைக்கு நன்றி. - PRAAN",
    },
    "error": {
        "en": "Sorry, something went wrong. Please try again or call our helpline. - PRAAN",
        "hi": "माफ़ करें, कुछ गलत हो गया। कृपया फिर से कोशिश करें। - PRAAN",
        "te": "క్షమించండి, ఏదో తప్పు జరిగింది. దయచేసి మళ్ళీ ప్రయత్నించండి. - PRAAN",
        "ta": "மன்னிக்கவும், ஏதோ தவறு நடந்தது. மீண்டும் முயற்சிக்கவும். - PRAAN",
    },
}

def _t(key: str, lang: str, **kwargs) -> str:
    msg = _T.get(key, {}).get(lang) or _T[key]["en"]
    return msg.format(**kwargs) if kwargs else msg

# ── Core send ─────────────────────────────────────────────
def _send(to_phone: str, body: str, simulate: bool = False) -> dict:
    to_wa = f"whatsapp:{to_phone}"
    print(f"[PRAAN WHATSAPP] → {to_wa}: {body}")
    return {"sid": "TELEGRAM_MODE", "to": to_wa, "body": body, "status": "logged"}

# ── Session helpers ───────────────────────────────────────
def _session(phone: str) -> dict:
    if phone not in _SESSIONS:
        _SESSIONS[phone] = {"state": "idle", "lang": "en", "data": {},
                            "history": deque(maxlen=5), "last_seen": None}
    return _SESSIONS[phone]

def _reset(phone: str):
    s = _session(phone)
    s["state"] = "idle"
    s["data"]  = {}

# ── Patient bot entry point ───────────────────────────────
def handle_patient_message(phone: str, body: str, db) -> str:
    """
    Main conversational router. Returns the reply text (also sends it).
    phone: E.164 e.g. +919845001001
    """
    from models import Patient, Donor, TransfusionRequest, DonorMatch
    from datetime import date

    s    = _session(phone)
    text = body.strip()
    s["history"].append({"from": "user", "text": text, "ts": datetime.now(timezone.utc)})

    # Language detection on first message or re-detect if idle
    if s["state"] == "idle":
        s["lang"] = _detect_lang(text)
    lang = s["lang"]

    # ── Donor reactivation check ──────────────────────────
    # If a known donor who previously had a match says YES again
    if text.lower() in {"yes", "हाँ", "అవును", "ஆம்"}:
        donor = db.query(Donor).filter(Donor.phone == phone).first()
        if donor:
            match = (db.query(DonorMatch)
                     .filter(DonorMatch.donor_id == donor.id, DonorMatch.confirmed == False)
                     .order_by(DonorMatch.created_at.desc()).first())
            if match:
                match.confirmed    = True
                match.confirmed_at = datetime.now(timezone.utc)
                db.commit()
                reply = _t("donor_reactivated", lang)
                _send(phone, reply)
                _log(f"Donor {donor.name} reactivated match via WhatsApp")
                _reset(phone)
                return reply

    # ── State machine ─────────────────────────────────────
    state = s["state"]

    # IDLE → show menu
    if state == "idle":
        reply = _t("welcome", lang)
        s["state"] = "menu"
        _send(phone, reply)
        return reply

    # MENU → handle choice
    if state == "menu":
        if text == "1":
            # Check for active request within 24 h
            patient = db.query(Patient).filter(Patient.phone == phone).first() if hasattr(Patient, "phone") else None
            # phones stored on donors table; try matching via donor
            if not patient:
                # look up by checking if phone matches any patient's linked donor
                # For hackathon: look for any TransfusionRequest created via whatsapp
                # for this phone in last 24h
                pass
            # Simpler: look up patient by checking sessions data
            existing_patient_id = s["data"].get("patient_id")
            if existing_patient_id:
                req = (db.query(TransfusionRequest)
                       .filter(TransfusionRequest.patient_id == existing_patient_id,
                               TransfusionRequest.status.in_(["pending","matched"]))
                       .order_by(TransfusionRequest.created_at.desc()).first())
                if req:
                    age_h = (datetime.now(timezone.utc) - req.created_at.replace(tzinfo=timezone.utc)).total_seconds() / 3600
                    if age_h < 24:
                        reply = _t("active_request", lang, status=req.status, urgency=req.urgency,
                                   date=str(req.predicted_date))
                        s["state"] = "confirm_new_request"
                        _send(phone, reply)
                        return reply
            s["state"] = "ask_phone"
            reply = _t("ask_phone", lang)
            _send(phone, reply)
            return reply

        elif text == "2":
            # Status check
            pid = s["data"].get("patient_id")
            if not pid:
                s["state"] = "ask_phone_status"
                reply = _t("ask_phone", lang)
                _send(phone, reply)
                return reply
            req = (db.query(TransfusionRequest)
                   .filter(TransfusionRequest.patient_id == pid)
                   .order_by(TransfusionRequest.created_at.desc()).first())
            if req:
                reply = _t("status_reply", lang, status=req.status,
                           urgency=req.urgency, date=str(req.predicted_date))
            else:
                reply = "No requests found for your profile. - PRAAN"
            _reset(phone)
            _send(phone, reply)
            return reply

        elif text == "3":
            s["state"] = "reg_donor_name"
            reply = _t("register_donor_ask", lang)
            _send(phone, reply)
            return reply

        else:
            reply = _t("welcome", lang)
            _send(phone, reply)
            return reply

    # CONFIRM NEW REQUEST (when active request exists)
    if state == "confirm_new_request":
        if text.lower() in {"yes", "हाँ", "అవును", "ஆம்"}:
            s["state"] = "ask_urgency"
            reply = _t("ask_urgency", lang)
            _send(phone, reply)
        else:
            _reset(phone)
            reply = "OK! Your existing request is still active. - PRAAN"
            _send(phone, reply)
        return reply

    # PHONE LOOKUP for blood request
    if state == "ask_phone":
        lookup_phone = text if text.startswith("+") else phone
        from models import Patient
        # Find patient by stored sessions or by phone field if it exists
        # Hackathon: use phone as patient lookup key via session
        # Attempt to find patient by phone stored in session history
        patient = _find_patient_by_phone(lookup_phone, db)
        if patient:
            s["data"]["patient_id"]   = str(patient.id)
            s["data"]["patient_name"] = patient.name
            s["data"]["blood_type"]   = patient.blood_type
            s["state"] = "ask_urgency"
            reply = _t("ask_urgency", lang)
        else:
            s["data"]["lookup_phone"] = lookup_phone
            s["state"] = "reg_name"
            reply = _t("not_registered", lang)
        _send(phone, reply)
        return reply

    # STATUS PHONE LOOKUP
    if state == "ask_phone_status":
        lookup_phone = text if text.startswith("+") else phone
        patient = _find_patient_by_phone(lookup_phone, db)
        if patient:
            req = (db.query(TransfusionRequest)
                   .filter(TransfusionRequest.patient_id == patient.id)
                   .order_by(TransfusionRequest.created_at.desc()).first())
            if req:
                reply = _t("status_reply", lang, status=req.status,
                           urgency=req.urgency, date=str(req.predicted_date))
            else:
                reply = "No requests found. - PRAAN"
        else:
            reply = "Phone not found in our system. - PRAAN"
        _reset(phone)
        _send(phone, reply)
        return reply

    # URGENCY for blood request
    if state == "ask_urgency":
        urgency = "urgent" if "urgent" in text.lower() else "normal"
        pid = s["data"].get("patient_id")
        if not pid:
            _reset(phone)
            reply = _t("error", lang)
            _send(phone, reply)
            return reply
        try:
            reply = _create_request_and_match(pid, urgency, lang, phone, db)
        except Exception as e:
            reply = _t("error", lang)
            print(f"[PRAAN] request creation error: {e}")
        _reset(phone)
        _send(phone, reply)
        return reply

    # REGISTRATION FLOW — new patient
    if state == "reg_name":
        s["data"]["reg_name"] = text
        s["state"] = "reg_blood"
        reply = _t("ask_blood_type", lang)
        _send(phone, reply)
        return reply

    if state == "reg_blood":
        s["data"]["reg_blood"] = text.upper()
        s["state"] = "reg_city"
        reply = _t("ask_city", lang)
        _send(phone, reply)
        return reply

    if state == "reg_city":
        from models import Patient
        import uuid as _uuid
        new_patient = Patient(
            id               = _uuid.uuid4(),
            name             = s["data"].get("reg_name", "Unknown"),
            blood_type       = s["data"].get("reg_blood", "O+"),
            city             = text,
            thalassemia_type = "beta-major",
        )
        db.add(new_patient)
        db.commit()
        db.refresh(new_patient)
        s["data"]["patient_id"]   = str(new_patient.id)
        s["data"]["patient_name"] = new_patient.name
        s["data"]["blood_type"]   = new_patient.blood_type
        s["state"] = "ask_urgency"
        _log(f"New patient {new_patient.name} registered via WhatsApp ({phone})")
        reply = _t("ask_urgency", lang)
        _send(phone, reply)
        return reply

    # DONOR REGISTRATION FLOW
    if state == "reg_donor_name":
        s["data"]["donor_name"] = text
        s["state"] = "reg_donor_blood"
        reply = _t("ask_blood_type", lang)
        _send(phone, reply)
        return reply

    if state == "reg_donor_blood":
        s["data"]["donor_blood"] = text.upper()
        s["state"] = "reg_donor_city"
        reply = _t("ask_city", lang)
        _send(phone, reply)
        return reply

    if state == "reg_donor_city":
        from models import Donor
        import uuid as _uuid
        existing = db.query(Donor).filter(Donor.phone == phone).first()
        if not existing:
            new_donor = Donor(
                id         = _uuid.uuid4(),
                name       = s["data"].get("donor_name", "Unknown"),
                phone      = phone,
                blood_type = s["data"].get("donor_blood", "O+"),
                city       = text,
                preferred_language = lang,
            )
            db.add(new_donor)
            db.commit()
            _log(f"New donor {new_donor.name} registered via WhatsApp ({phone})")
        _reset(phone)
        reply = _t("donor_registered", lang)
        _send(phone, reply)
        return reply

    # Fallback: restart
    _reset(phone)
    reply = _t("welcome", lang)
    s["state"] = "menu"
    _send(phone, reply)
    return reply


def _find_patient_by_phone(phone: str, db) -> object:
    """Look up patient by phone via session data or donor cross-reference."""
    from models import Patient
    # Check all sessions for this phone → patient_id mapping
    for p, sess in _SESSIONS.items():
        if sess["data"].get("lookup_phone") == phone or p == phone:
            pid = sess["data"].get("patient_id")
            if pid:
                from uuid import UUID
                return db.query(Patient).filter(Patient.id == UUID(pid)).first()
    # Fallback: try to find by city/name if stored
    return None


def _create_request_and_match(patient_id: str, urgency: str, lang: str, phone: str, db) -> str:
    """Create TransfusionRequest + trigger matching as background-style call."""
    from models import Patient, TransfusionRequest, DonorMatch
    from matcher import match_donors_for_patient
    from datetime import date, timedelta
    import uuid as _uuid

    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        return _t("error", lang)

    days_ahead = 1 if urgency == "urgent" else 7
    req = TransfusionRequest(
        id             = _uuid.uuid4(),
        patient_id     = patient.id,
        predicted_date = date.today() + timedelta(days=days_ahead),
        urgency        = urgency,
        status         = "pending",
        notes          = f"Raised via WhatsApp by {phone}",
        raised_by      = "whatsapp",
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    _log(f"Patient {patient.name} raised {urgency} request via WhatsApp", "info")

    # Trigger matching immediately
    scored_donors, _ = match_donors_for_patient(patient, db, limit=5)
    now = datetime.now(timezone.utc)
    for entry in scored_donors[:3]:
        from uuid import UUID
        donor_uuid = UUID(entry["donor_id"])
        db.add(DonorMatch(
            request_id  = req.id,
            donor_id    = donor_uuid,
            match_score = round(entry["match_score"], 2),
            notified_at = now,
        ))
        # Notify each donor
        from models import Donor
        donor = db.query(Donor).filter(Donor.id == donor_uuid).first()
        if donor:
            send_donation_request(
                {"name": donor.name, "phone": donor.phone,
                 "language": donor.preferred_language, "blood_type": donor.blood_type},
                {"blood_type": patient.blood_type},
                str(req.id),
            )

    req.status = "matched"
    db.commit()
    _log(f"3 donors notified automatically for {patient.name}'s request", "info")
    return _t("request_created", lang)


# ── Existing donor-facing functions (unchanged) ───────────

_TEMPLATES = {
    "en": ("Hi {name}! A Thalassemia patient near you urgently needs {blood_type} blood. "
           "Can you donate? Reply YES to confirm or NO to decline. - PRAAN Blood Warriors"),
    "hi": ("नमस्ते {name}! आपके पास एक थैलेसीमिया रोगी को {blood_type} रक्त की जरूरत है। "
           "क्या आप दान कर सकते हैं? YES या NO लिखें। - PRAAN"),
    "te": ("హలో {name}! మీ దగ్గర ఒక థాలసీమియా రోగికి {blood_type} రక్తం అవసరం. "
           "దానం చేయగలరా? YES లేదా NO అని reply చేయండి. - PRAAN"),
    "ta": ("வணக்கம் {name}! உங்களுக்கு அருகில் ஒரு தலசீமியா நோயாளிக்கு {blood_type} இரத்தம் தேவை. "
           "தானம் செய்வீர்களா? YES அல்லது NO பதில் அனுப்பவும். - PRAAN"),
}

_CONFIRM_MSG = {
    "en": "✅ Thank you {name}! Your donation has been confirmed. The care team will contact you shortly. - PRAAN",
    "hi": "✅ धन्यवाद {name}! आपका दान स्वीकार किया गया है। टीम जल्द संपर्क करेगी। - PRAAN",
    "te": "✅ ధన్యవాదాలు {name}! మీ దానం నిర్ధారించబడింది. బృందం త్వరలో సంప్రదిస్తుంది. - PRAAN",
    "ta": "✅ நன்றி {name}! உங்கள் தானம் உறுதிப்படுத்தப்பட்டது. குழு விரைவில் தொடர்பு கொள்ளும். - PRAAN",
}

_DECLINE_MSG = {
    "en": "No problem {name}. We'll reach out to another donor. Thank you for responding! - PRAAN",
    "hi": "कोई बात नहीं {name}। हम किसी अन्य दाता से संपर्क करेंगे। जवाब देने के लिए शुक्रिया! - PRAAN",
    "te": "పర్వాలేదు {name}. మేము మరొక దాత్రుడిని సంప్రదిస్తాము. స్పందించినందుకు ధన్యవాదాలు! - PRAAN",
    "ta": "பரவாயில்லை {name}. நாங்கள் வேறொரு தானியாளரை தொடர்பு கொள்கிறோம். பதில் அனுப்பியதற்கு நன்றி! - PRAAN",
}

_YES_WORDS = {"yes", "हाँ", "అవును", "ஆம்"}
_NO_WORDS  = {"no",  "नहीं", "కాదు",  "இல்லை"}


def send_donation_request(donor: dict, patient: dict, request_id: str, simulate: bool = False) -> dict:
    lang = (donor.get("language") or donor.get("preferred_language") or "en").lower()
    lang = lang if lang in _TEMPLATES else "en"
    body = _TEMPLATES[lang].format(name=donor["name"], blood_type=patient["blood_type"])
    return _send(donor["phone"], body, simulate=simulate)


def send_impact_message(donor: dict, patient_name: str, simulate: bool = False) -> dict:
    body = (f"Thanks to you {donor['name']}, {patient_name} completed their transfusion today. "
            "Your donation made a real difference. Thank you from Blood Warriors. 🩸")
    return _send(donor["phone"], body, simulate=simulate)


def _confirm_match_by_phone(phone: str, db) -> tuple[bool, object | None]:
    from models import DonorMatch, Donor
    donor = db.query(Donor).filter(Donor.phone == phone).first()
    if not donor:
        return False, None
    match = (db.query(DonorMatch)
             .filter(DonorMatch.donor_id == donor.id, DonorMatch.confirmed == False)
             .order_by(DonorMatch.created_at.desc()).first())
    if not match:
        return False, None
    match.confirmed    = True
    match.confirmed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(match)
    _log(f"Donor {donor.name} confirmed match via WhatsApp", "info")
    return True, match


def _decline_match_by_phone(phone: str, db) -> tuple[bool, object | None]:
    from models import DonorMatch, Donor
    donor = db.query(Donor).filter(Donor.phone == phone).first()
    if not donor:
        return False, None
    declined_match = (db.query(DonorMatch)
                      .filter(DonorMatch.donor_id == donor.id, DonorMatch.confirmed == False)
                      .order_by(DonorMatch.created_at.desc()).first())
    if not declined_match:
        return False, None
    next_match = (db.query(DonorMatch)
                  .filter(DonorMatch.request_id == declined_match.request_id,
                          DonorMatch.donor_id   != donor.id,
                          DonorMatch.confirmed  == False,
                          DonorMatch.notified_at == None)
                  .order_by(DonorMatch.match_score.desc()).first())
    if not next_match:
        return False, None
    _log(f"Donor {donor.name} declined; cascading to next donor", "warn")
    return True, next_match


def simulate_whatsapp_flow(patient_id: str, db) -> None:
    from models import Patient, DonorMatch, Donor, TransfusionRequest
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        print(f"[SIMULATE] Patient {patient_id} not found.")
        return
    req = (db.query(TransfusionRequest)
           .filter(TransfusionRequest.patient_id == patient.id,
                   TransfusionRequest.status == "matched")
           .order_by(TransfusionRequest.created_at.desc()).first())
    if not req:
        print(f"[SIMULATE] No matched request found for patient {patient.name}.")
        return
    matches = (db.query(DonorMatch)
               .filter(DonorMatch.request_id == req.id)
               .order_by(DonorMatch.match_score.desc()).all())
    print(f"\n{'='*60}\n  PRAAN WhatsApp Flow Simulation")
    print(f"  Patient : {patient.name} ({patient.blood_type}, {patient.city})")
    print(f"  Request : {req.id}  urgency={req.urgency}\n{'='*60}")
    for i, m in enumerate(matches):
        donor = db.query(Donor).filter(Donor.id == m.donor_id).first()
        if not donor:
            continue
        result = send_donation_request(
            {"name": donor.name, "phone": donor.phone,
             "language": donor.preferred_language, "blood_type": donor.blood_type},
            {"blood_type": patient.blood_type}, str(req.id), simulate=True)
        print(f"\n  [{i+1}] → {donor.name} ({donor.phone})  score={m.match_score}")
        print(f"       MSG : {result['body']}")
        if i == 0:
            print(f"       ← Donor replies: YES")
            impact = send_impact_message(
                {"name": donor.name, "phone": donor.phone, "language": donor.preferred_language},
                patient.name, simulate=True)
            print(f"       IMPACT MSG: {impact['body']}")
        else:
            print(f"       (on standby)")
    print(f"\n{'='*60}\n")
