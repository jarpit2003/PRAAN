# ─────────────────────────────────────────────────────────────────────────────
#  PRAAN Blood Warriors — Telegram Bot  (Veeru)
#  Bedrock = field collection only. Bot owns all action execution.
# ─────────────────────────────────────────────────────────────────────────────

import os
import re
import json
import asyncio
import httpx
import boto3

from datetime import date, timedelta, datetime, timezone
from dotenv import load_dotenv

from telegram import Update, Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters,
)

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
PRAAN_API          = os.getenv("PRAAN_API_URL", "http://localhost:8000")
AWS_REGION         = os.getenv("AWS_REGION", "us-east-1")
BEDROCK_MODEL      = os.getenv("BEDROCK_MODEL", "amazon.nova-micro-v1:0")

PATIENT_TELEGRAM_ID = 1104538282   # @shivane431
DONOR_TELEGRAM_ID   = 5079575913   # @Arpit_1710_2003
KANAV_TELEGRAM_ID   = int(os.getenv("KANAV_TELEGRAM_ID", "0"))

KANAV_PATIENT_ID  = "851252fd-0be4-47c3-96c2-956964be1305"
KANAV_BLOOD_TYPE  = "B+"
KANAV_NAME        = "Kanav"

# ── In-memory state ───────────────────────────────────────
# session keys: history, patient_id, pending_action, flow, fields
sessions:          dict[str, dict] = {}
pending_donations: dict[str, dict] = {}
pending_reschedule: dict[str, str] = {}

YES_WORDS = {"yes","y","haan","ha","yep","ok","okay","हाँ","ji","haa","confirm","sahi","bilkul"}
NO_WORDS  = {"no","n","nope","nahi","नहीं","na","naa","galat","change"}

INDIA_CITIES = {
    "delhi","new delhi","mumbai","bombay","bengaluru","bangalore",
    "chennai","madras","hyderabad","kolkata","calcutta","pune",
    "ahmedabad","jaipur","surat","lucknow","kanpur","nagpur",
    "indore","thane","bhopal","visakhapatnam","vizag","patna",
    "vadodara","ghaziabad","ludhiana","agra","nashik","faridabad",
    "meerut","rajkot","varanasi","srinagar","aurangabad","dhanbad",
    "amritsar","allahabad","prayagraj","ranchi","coimbatore",
    "jabalpur","gwalior","vijayawada","jodhpur","madurai","raipur",
    "kota","guwahati","chandigarh","solapur","hubli","dharwad",
    "bareilly","moradabad","mysuru","mysore","gurgaon","gurugram",
    "aligarh","jalandhar","tiruchirappalli","trichy","bhubaneswar",
    "salem","mira bhayandar","warangul","guntur","bhiwandi",
    "saharanpur","gorakhpur","bikaner","amravati","noida",
    "jamshedpur","bhilai","cuttack","firozabad","kochi","cochin",
    "nellore","jammu","dehradun","shimla","mangaluru","mangalore",
    "muktsar","bathinda","patiala","mohali","ambala","karnal",
    "panipat","rohtak","hisar","udaipur","ajmer","sikar",
    "bilaspur","durg","korba","tirupati","kurnool","anantapur",
    "rajahmundry","eluru","kakinada","kadapa",
}

VALID_BLOOD = {"O+","O-","A+","A-","B+","B-","AB+","AB-"}


def normalize_city(raw: str) -> str | None:
    c = raw.strip().lower()
    if c in INDIA_CITIES:
        return raw.strip().title()
    if len(c) >= 4:
        matches = [x for x in INDIA_CITIES if x.startswith(c[:4])]
        if len(matches) == 1:
            return matches[0].title()
    return None


def normalize_blood_type(raw: str) -> str | None:
    raw = raw.upper().strip()
    if raw in VALID_BLOOD:
        return raw
    word_map = {
        "O POSITIVE":"O+","O NEGATIVE":"O-","A POSITIVE":"A+","A NEGATIVE":"A-",
        "B POSITIVE":"B+","B NEGATIVE":"B-","AB POSITIVE":"AB+","AB NEGATIVE":"AB-",
        "O POS":"O+","O NEG":"O-","A POS":"A+","A NEG":"A-",
        "B POS":"B+","B NEG":"B-","AB POS":"AB+","AB NEG":"AB-",
        "O+VE":"O+","O-VE":"O-","A+VE":"A+","A-VE":"A-",
        "B+VE":"B+","B-VE":"B-","AB+VE":"AB+","AB-VE":"AB-",
    }
    if raw in word_map:
        return word_map[raw]
    m = re.search(r'\b(AB[+-]|[ABO][+-])\b', raw)
    return m.group(1) if m else None


# ── Bedrock ───────────────────────────────────────────────

_bedrock = None

def get_bedrock():
    global _bedrock
    if _bedrock is None:
        try:
            _bedrock = boto3.client("bedrock-runtime", region_name=AWS_REGION)
        except Exception as e:
            print(f"[BEDROCK] Init failed: {e}")
    return _bedrock


def bedrock_chat(system: str, history: list, user_msg: str) -> str:
    bedrock = get_bedrock()
    if not bedrock:
        return ""
    messages = [{"role": h["role"], "content": [{"text": h["content"]}]} for h in history]
    messages.append({"role": "user", "content": [{"text": user_msg}]})
    body = json.dumps({
        "system": [{"text": system}],
        "messages": messages,
        "inferenceConfig": {"maxTokens": 400, "temperature": 0.2},
    })
    try:
        resp = bedrock.invoke_model(modelId=BEDROCK_MODEL, body=body)
        return json.loads(resp["body"].read())["output"]["message"]["content"][0]["text"].strip()
    except Exception as e:
        print(f"[BEDROCK] Chat failed: {e}")
        return ""


# ── Bedrock: extract structured fields from conversation ──

EXTRACT_SYSTEM = """You are a data extraction assistant.
Given a conversation between a user and Veeru (a blood request bot), extract the collected fields as JSON.

Return ONLY valid JSON, nothing else. No explanation, no markdown.

For blood request return:
{"type":"request","name":"...","blood_type":"...","gender":"...","city":"...","location":"...","urgency":"urgent/normal","required_date":"YYYY-MM-DD"}

For donor registration return:
{"type":"donor","name":"...","blood_type":"...","gender":"...","city":"...","donated_earlier":true/false,"last_donation_date":"YYYY-MM-DD or null"}

If fields are missing or unclear use null.
urgency: use "urgent" if user said emergency/urgent/jaldi/abhi/turant, else "normal".
required_date: today is """ + str(date.today()) + """. "aaj"=today, "kal"=tomorrow."""


def extract_fields_from_history(history: list) -> dict | None:
    """Ask Bedrock to extract structured fields from the full conversation."""
    if not history:
        return None
    convo = "\n".join(
        f"{'User' if h['role']=='user' else 'Veeru'}: {h['content']}"
        for h in history
    )
    bedrock = get_bedrock()
    if not bedrock:
        return None
    body = json.dumps({
        "system": [{"text": EXTRACT_SYSTEM}],
        "messages": [{"role": "user", "content": [{"text": convo}]}],
        "inferenceConfig": {"maxTokens": 300, "temperature": 0.0},
    })
    try:
        resp = bedrock.invoke_model(modelId=BEDROCK_MODEL, body=body)
        raw = json.loads(resp["body"].read())["output"]["message"]["content"][0]["text"].strip()
        # strip markdown code fences if present
        raw = re.sub(r'^```[a-z]*\n?', '', raw).rstrip('`').strip()
        return json.loads(raw)
    except Exception as e:
        print(f"[EXTRACT] Failed: {e}")
        return None


# ── Session ───────────────────────────────────────────────

def get_session(uid: str) -> dict:
    if uid not in sessions:
        sessions[uid] = {
            "history": [],
            "patient_id": None,
            "pending_action": None,   # confirmed action waiting to execute
            "awaiting_confirm": False, # True when summary shown, waiting YES/NO
        }
    return sessions[uid]


# ── System prompt for Veeru (conversation only, NO ACTION output) ─────────

VEERU_SYSTEM = f"""You are Veeru, a warm and helpful assistant for PRAAN Blood Warriors — a platform connecting Thalassemia patients with blood donors across India.

=== LANGUAGE RULE ===
Always reply in the same language the user writes in. Switch immediately if they switch.
NEVER include policy text, disclaimers, or copyright notices.

=== YOUR ONLY PURPOSES ===
1. Help a patient/guardian create a blood request
2. Register someone as a blood donor
3. Check status of an existing request

For anything else say: "I can only help with blood donation requests. — Veeru 🩸"

=== INDIA ONLY ===
PRAAN only operates in India. Reject foreign cities politely.

=== CITY vs LOCATION ===
- city = real Indian city (Delhi, Mumbai, Patiala, etc.)
- location = specific area/colony/sector within that city
Ask them separately. Validate both.

=== BLOOD TYPE ===
Valid: O+, O-, A+, A-, B+, B-, AB+, AB-
Normalise variants (O positive → O+, A-ve → A-, etc.)

=== CONVERSATION RULES ===
- ONE question at a time
- Never repeat a question already answered
- "kal" = tomorrow ({date.today() + timedelta(days=1)}), "aaj" = today ({date.today()})
- Urgency words: emergency/urgent/asap/abhi/jaldi/turant → urgent
- required_date must be >= today ({date.today()})

=== REQUIRED FIELDS ===
Blood request: name, blood_type, gender, city, location, urgency, required_date
Donor: name, blood_type, gender, city, donated_earlier, last_donation_date (if donated)

=== CONFIRMATION ===
Once ALL fields collected, show a clean bullet-point summary and ask:
"Is this correct? Please confirm with YES or NO — Veeru 🩸"

DO NOT output any ACTION, JSON, or code. Just collect fields and show the summary.
The system will handle the actual request creation automatically after user confirms.

Always end messages with "— Veeru 🩸"
"""


# ── Build confirmation summary from extracted fields ──────

def build_summary(fields: dict) -> str:
    if fields.get("type") == "request":
        return (
            f"Here's a summary of your blood request:\n\n"
            f"👤 Patient: *{fields.get('name') or '—'}*\n"
            f"🩸 Blood type: *{fields.get('blood_type') or '—'}*\n"
            f"⚧ Gender: {fields.get('gender') or '—'}\n"
            f"🏙 City: {fields.get('city') or '—'}\n"
            f"📍 Location: {fields.get('location') or '—'}\n"
            f"🚨 Urgency: {str(fields.get('urgency') or 'normal').title()}\n"
            f"📅 Required by: {fields.get('required_date') or date.today()}\n\n"
            f"Is this correct? Reply *YES* to confirm or *NO* to change something. — Veeru 🩸"
        )
    elif fields.get("type") == "donor":
        return (
            f"Here's your donor registration summary:\n\n"
            f"👤 Name: *{fields.get('name') or '—'}*\n"
            f"🩸 Blood type: *{fields.get('blood_type') or '—'}*\n"
            f"⚧ Gender: {fields.get('gender') or '—'}\n"
            f"🏙 City: {fields.get('city') or '—'}\n"
            f"💉 Donated before: {'Yes' if fields.get('donated_earlier') else 'No'}\n\n"
            f"Is this correct? Reply *YES* to confirm or *NO* to change something. — Veeru 🩸"
        )
    return ""


def fields_complete(fields: dict) -> bool:
    if not fields:
        return False
    if fields.get("type") == "request":
        required = ["name", "blood_type", "gender", "city", "location", "urgency", "required_date"]
    elif fields.get("type") == "donor":
        required = ["name", "blood_type", "gender", "city"]
    else:
        return False
    return all(fields.get(k) not in (None, "", "null") for k in required)


# ── Action execution ──────────────────────────────────────

async def execute_action(uid: str, fields: dict, update: Update, context: ContextTypes.DEFAULT_TYPE):
    s = get_session(uid)

    if fields.get("type") == "request":
        name       = fields.get("name", "")
        blood_type = normalize_blood_type(fields.get("blood_type", "")) or fields.get("blood_type", "")
        city_raw   = fields.get("city", "")
        city       = normalize_city(city_raw) or city_raw.title()
        location   = fields.get("location", city)
        urgency    = fields.get("urgency", "normal")
        req_date   = fields.get("required_date", str(date.today()))

        # Register patient
        patient_id = s.get("patient_id")
        if not patient_id:
            try:
                r = httpx.post(f"{PRAAN_API}/patients/register", json={
                    "name": name, "blood_type": blood_type,
                    "city": city, "phone": uid,
                }, timeout=10)
                r.raise_for_status()
                patient_id = r.json().get("id")
                s["patient_id"] = patient_id
                print(f"[FLOW1] Patient registered: {patient_id}")
            except Exception as e:
                print(f"[BOT] Register error: {e}")
                await update.message.reply_text(
                    "⚠️ Could not register patient. Please try again. — Veeru 🩸"
                )
                return

        # Create request
        request_id = None
        if patient_id:
            try:
                r = httpx.post(f"{PRAAN_API}/bot/request", json={
                    "patient_id": patient_id, "urgency": urgency,
                    "phone": uid, "location": location,
                }, timeout=15)
                r.raise_for_status()
                request_id = r.json().get("request_id")
                print(f"[FLOW1] Request created: {request_id}")
            except Exception as e:
                print(f"[BOT] Request error: {e}")
                await update.message.reply_text(
                    "⚠️ Could not create the request. Please try again. — Veeru 🩸"
                )
                return

        await update.message.reply_text(
            f"✅ *Blood request created!*\n\n"
            f"🆔 ID: `{(request_id or 'N/A')[:8]}`\n"
            f"👤 Patient: *{name}*\n"
            f"🩸 Blood type: *{blood_type}*\n"
            f"📍 Location: {location}, {city}\n"
            f"🚨 Urgency: {urgency.title()}\n"
            f"📅 Required by: {req_date}\n\n"
            f"🔍 Finding the best matched donor now...\n"
            f"You'll be notified once a donor confirms. — Veeru 🩸",
            parse_mode="Markdown",
        )
        s["history"] = []
        s["pending_action"] = None
        s["awaiting_confirm"] = False

        if request_id:
            asyncio.create_task(run_flow2_matching(
                request_id=request_id, bot=context.bot,
                patient_blood=blood_type, urgency=urgency,
                patient_telegram_id=PATIENT_TELEGRAM_ID,
            ))

    elif fields.get("type") == "donor":
        name            = fields.get("name", "")
        blood_type      = normalize_blood_type(fields.get("blood_type", "")) or fields.get("blood_type", "")
        city_raw        = fields.get("city", "")
        city            = normalize_city(city_raw) or city_raw.title()
        gender          = fields.get("gender", "")
        donated_earlier = fields.get("donated_earlier", False)
        last_donation   = fields.get("last_donation_date") or None

        try:
            r = httpx.post(f"{PRAAN_API}/donors/register", json={
                "name": name, "blood_type": blood_type, "city": city,
                "phone": uid, "gender": gender,
                "donated_earlier": donated_earlier,
                "last_donation_date": last_donation,
            }, timeout=10)
            r.raise_for_status()
        except Exception as e:
            print(f"[BOT] Donor register error: {e}")
            await update.message.reply_text(
                "⚠️ Could not register donor. Please try again. — Veeru 🩸"
            )
            return

        await update.message.reply_text(
            f"🎉 *Registered as a donor!*\n"
            f"Name: {name} | Blood: {blood_type} | City: {city}\n\n"
            f"We'll reach out when a nearby patient needs your blood type.\n"
            f"Thank you for saving lives! — Veeru 🩸",
            parse_mode="Markdown",
        )
        s["history"] = []
        s["pending_action"] = None
        s["awaiting_confirm"] = False


# ── Transfusion reminder ──────────────────────────────────

async def send_transfusion_reminder(bot: Bot, transfusion_date: str):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Confirm",    callback_data=f"remind:confirm:{transfusion_date}")],
        [InlineKeyboardButton("❌ Not Needed", callback_data=f"remind:not_needed:{transfusion_date}")],
        [InlineKeyboardButton("📅 Reschedule", callback_data=f"remind:reschedule:{transfusion_date}")],
    ])
    await bot.send_message(
        chat_id=KANAV_TELEGRAM_ID,
        text=(
            f"🩸 *Transfusion Reminder*\n\n"
            f"Hi {KANAV_NAME}! Your next predicted transfusion date is:\n"
            f"📅 *{transfusion_date}*\n\n"
            f"Blood type needed: *{KANAV_BLOOD_TYPE}*\n\n"
            f"Please choose an option below:"
        ),
        parse_mode="Markdown",
        reply_markup=keyboard,
    )
    print(f"[REMINDER] Sent to Kanav for date {transfusion_date}")


async def handle_reminder_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts      = query.data.split(":")
    action     = parts[1]
    trans_date = parts[2]
    uid        = str(query.from_user.id)

    if action == "confirm":
        await query.edit_message_text(
            f"✅ *Confirmed!*\n\nCreating a blood request for *{trans_date}*...\n"
            f"Finding the best matched donor for you. — Veeru 🩸",
            parse_mode="Markdown",
        )
        await _create_and_notify(context.bot, trans_date, "normal")
    elif action == "not_needed":
        await query.edit_message_text(
            "👍 Got it! No transfusion needed at this time.\n"
            "We'll remind you again closer to the next predicted date. — Veeru 🩸"
        )
    elif action == "reschedule":
        pending_reschedule[uid] = trans_date
        await query.edit_message_text(
            "📅 *Reschedule*\n\nPlease reply with your preferred date\n"
            "Format: *DD-MM-YYYY* — Veeru 🩸",
            parse_mode="Markdown",
        )


async def _create_and_notify(bot: Bot, req_date: str, urgency: str):
    try:
        r = httpx.post(f"{PRAAN_API}/bot/request", json={
            "patient_id": KANAV_PATIENT_ID,
            "urgency":    urgency,
            "phone":      str(KANAV_TELEGRAM_ID),
            "location":   "Delhi",
        }, timeout=15)
        r.raise_for_status()
        request_id = r.json().get("request_id")
        print(f"[REMINDER] Request created: {request_id}")
        if request_id:
            asyncio.create_task(run_flow2_matching(
                request_id=request_id, bot=bot,
                patient_blood=KANAV_BLOOD_TYPE, urgency=urgency,
                patient_telegram_id=KANAV_TELEGRAM_ID,
            ))
    except Exception as e:
        print(f"[REMINDER] Request creation failed: {e}")


# ── Flow 2 — matching ────────────────────────────────────

async def run_flow2_matching(request_id: str, bot: Bot,
                              patient_blood: str, urgency: str,
                              patient_telegram_id: int):
    print(f"[FLOW2] Matching for {request_id[:8]}")
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(f"{PRAAN_API}/requests/{request_id}/match/run")
            if r.status_code != 200:
                print(f"[FLOW2] {r.status_code}: {r.text}")
                return
            donors = r.json()
            if not donors:
                print("[FLOW2] No donors returned")
                return
        top = donors[0]
        print(f"[FLOW2] Top donor blood={top.get('blood_type')} dist={top.get('distance_km')}km final={top.get('final_score')}")
        pending_donations[request_id] = {
            "patient_telegram_id": patient_telegram_id,
            "donor_telegram_id":   DONOR_TELEGRAM_ID,
            "blood_type":          patient_blood,
            "urgency":             urgency,
            "notified_at":         datetime.now(timezone.utc),
            "donor_score":         top.get("final_score", 0),
            "distance_km":         top.get("distance_km", 0),
        }
        await run_flow3_outreach(request_id, bot)
    except Exception as e:
        print(f"[FLOW2] Error: {e}")


# ── Flow 3 — donor outreach ──────────────────────────────

async def run_flow3_outreach(request_id: str, bot: Bot):
    info = pending_donations.get(request_id)
    if not info:
        return
    blood   = info["blood_type"]
    urgency = info["urgency"]
    dist    = info.get("distance_km", 0)
    score   = info.get("donor_score", 0)

    donor_msg = bedrock_chat(
        "Write short urgent blood donation Telegram messages. English only. 2 sentences max.",
        [],
        f"Write a warm message asking a donor to donate {blood} blood. Urgency: {urgency}. End with '- PRAAN Blood Warriors'.",
    ) or f"🩸 A Thalassemia patient urgently needs {blood} blood. Can you help? - PRAAN Blood Warriors"

    full_msg = (
        f"🩸 *Blood Donation Request*\n\n"
        f"{donor_msg}\n\n"
        f"📊 Match Score: {score:.3f}\n"
        f"📍 Distance: {dist} km\n"
        f"🆔 Request ID: `{request_id[:8]}`\n\n"
        f"Reply *YES* to confirm or *NO* to decline."
    )
    try:
        await bot.send_message(chat_id=info["donor_telegram_id"], text=full_msg, parse_mode="Markdown")
        print(f"[FLOW3] Message sent to donor {info['donor_telegram_id']}")
    except Exception as e:
        print(f"[FLOW3] Failed to message donor: {e}")
        return
    asyncio.create_task(_escalation_timer(request_id, bot))


async def _escalation_timer(request_id: str, bot: Bot):
    await asyncio.sleep(30 * 60)
    info = pending_donations.get(request_id)
    if not info:
        return
    print(f"[FLOW3] 30-min timeout for {request_id[:8]}")
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(f"{PRAAN_API}/requests/{request_id}/escalate")
    except Exception:
        pass
    try:
        await bot.send_message(
            chat_id=info["patient_telegram_id"],
            text="⚠️ No donor responded in 30 minutes. Our coordinator has been alerted. — Veeru 🩸",
        )
    except Exception as e:
        print(f"[FLOW3] Escalation alert failed: {e}")
    pending_donations.pop(request_id, None)


async def _handle_donor_yes(request_id: str, bot: Bot):
    info = pending_donations.pop(request_id, None)
    if not info:
        return
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(f"{PRAAN_API}/requests/{request_id}/escalate")
    except Exception:
        pass
    try:
        await bot.send_message(
            chat_id=info["patient_telegram_id"],
            text=(
                f"✅ *Great news!* A donor confirmed for your blood request 🩸\n\n"
                f"Blood type: *{info['blood_type']}*\n"
                f"Request ID: `{request_id[:8]}`\n\n"
                "The care team will contact you with donor details shortly.\n— Veeru 🩸"
            ),
            parse_mode="Markdown",
        )
    except Exception as e:
        print(f"[FLOW3] Patient notify failed: {e}")


async def _handle_donor_no(request_id: str, bot: Bot):
    info = pending_donations.pop(request_id, None)
    if not info:
        return
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(f"{PRAAN_API}/requests/{request_id}/escalate")
    except Exception:
        pass
    try:
        await bot.send_message(
            chat_id=info["patient_telegram_id"],
            text="⚠️ The matched donor is unavailable. Our coordinator will find an alternative. — Veeru 🩸",
        )
    except Exception as e:
        print(f"[FLOW3] Patient alert failed: {e}")


# ── Main handler ──────────────────────────────────────────

async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid       = str(update.effective_user.id)
    msg       = update.message.text.strip()
    msg_lower = msg.lower()
    print(f"[MSG] {uid}: {msg}")

    # ── Kanav: only reschedule flow ───────────────────────
    if uid == str(KANAV_TELEGRAM_ID):
        if uid not in pending_reschedule:
            return
    if uid in pending_reschedule:
        pending_reschedule.pop(uid)
        new_date = None
        for fmt in ("%d-%m-%Y", "%Y-%m-%d"):
            try:
                new_date = datetime.strptime(msg, fmt).date()
                break
            except ValueError:
                continue
        if not new_date or new_date < date.today():
            pending_reschedule[uid] = msg
            await update.message.reply_text(
                "⚠️ Invalid or past date. Please send as DD-MM-YYYY (e.g. 20-07-2026) — Veeru 🩸"
            )
            return
        date_str = new_date.strftime("%Y-%m-%d")
        await update.message.reply_text(
            f"✅ *Rescheduled!*\n\nCreating a blood request for *{date_str}*...\n"
            f"Finding the best matched donor for you. — Veeru 🩸",
            parse_mode="Markdown",
        )
        await _create_and_notify(context.bot, date_str, "normal")
        return

    # ── Donor YES/NO ──────────────────────────────────────
    if uid == str(DONOR_TELEGRAM_ID) and pending_donations:
        if msg_lower in YES_WORDS or msg_lower in NO_WORDS:
            target = next(
                (rid for rid, info in pending_donations.items()
                 if info["donor_telegram_id"] == int(uid)),
                None,
            )
            if target:
                if msg_lower in YES_WORDS:
                    await update.message.reply_text(
                        "✅ Thank you! Your donation is confirmed.\n"
                        "The care team will share patient details shortly. — Veeru 🩸"
                    )
                    await _handle_donor_yes(target, context.bot)
                else:
                    await update.message.reply_text(
                        "Understood. No problem! Thank you for responding. — Veeru 🩸"
                    )
                    await _handle_donor_no(target, context.bot)
                return

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    s = get_session(uid)

    # ── YES/NO when awaiting confirmation ─────────────────
    if s.get("awaiting_confirm"):
        if msg_lower in YES_WORDS:
            fields = s.get("pending_action")
            if fields:
                s["awaiting_confirm"] = False
                await execute_action(uid, fields, update, context)
            else:
                s["awaiting_confirm"] = False
                await update.message.reply_text("Something went wrong. Please start again. — Veeru 🩸")
            return
        elif msg_lower in NO_WORDS:
            s["awaiting_confirm"] = False
            s["pending_action"]   = None
            await update.message.reply_text(
                "No problem! What would you like to change? — Veeru 🩸"
            )
            return
        # Any other message while awaiting confirm — re-ask
        await update.message.reply_text(
            "Please reply with *YES* to confirm or *NO* to change something. — Veeru 🩸",
            parse_mode="Markdown",
        )
        return

    # ── Bedrock conversation ──────────────────────────────
    reply = bedrock_chat(VEERU_SYSTEM, s["history"], msg)

    if not reply:
        await update.message.reply_text(
            "Hi! I'm Veeru from PRAAN Blood Warriors 🩸\n"
            "I can help you request blood or register as a donor. What do you need?"
        )
        return

    # Strip leaked policy text
    for marker in ["Only reproduce, summarize", "Media Outlets Policy",
                   "Generate a polite, respectful", "Ensure that all responses remain"]:
        idx = reply.find(marker)
        if idx != -1:
            reply = reply[:idx].strip()

    # Update history
    s["history"].append({"role": "user",      "content": msg})
    s["history"].append({"role": "assistant",  "content": reply})
    if len(s["history"]) > 20:
        s["history"] = s["history"][-20:]

    # ── Detect if Bedrock has shown a summary / asked for confirm ──
    reply_lower = reply.lower()
    confirm_phrases = [
        "is this correct", "please confirm", "confirm with yes",
        "reply yes", "reply with yes", "sahi hai", "confirm karen",
        "shall i proceed",
    ]
    bedrock_asking_confirm = any(p in reply_lower for p in confirm_phrases)

    if bedrock_asking_confirm:
        # Extract structured fields from conversation history
        fields = extract_fields_from_history(s["history"])
        print(f"[EXTRACT] fields={fields}")

        if fields and fields_complete(fields):
            # Normalise blood type
            if fields.get("blood_type"):
                fields["blood_type"] = normalize_blood_type(fields["blood_type"]) or fields["blood_type"]
            # Store and show our own clean summary instead of Bedrock's
            s["pending_action"]   = fields
            s["awaiting_confirm"] = True
            summary = build_summary(fields)
            await update.message.reply_text(summary, parse_mode="Markdown")
            return
        else:
            # Fields incomplete — let Bedrock reply go through as-is
            # but flag that we're trying to confirm
            s["awaiting_confirm"] = False

    await update.message.reply_text(reply)


# ── Entry point ───────────────────────────────────────────

def main():
    print("🩸 PRAAN Veeru Bot — Bedrock field collection, bot-owned execution")
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
    app.add_handler(CallbackQueryHandler(handle_reminder_callback, pattern=r"^remind:"))
    print("✅ Bot polling. Press Ctrl+C to stop.")
    app.run_polling()


if __name__ == "__main__":
    main()
