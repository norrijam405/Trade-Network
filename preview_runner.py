from pathlib import Path
import json
import os

import psycopg
from fastapi.responses import JSONResponse

source_path = Path(__file__).with_name("hosted_preview.py")
source = source_path.read_text(encoding="utf-8")
stripped = source.rstrip()
if stripped.endswith('"""'):
    stripped = stripped[:-3].rstrip() + "\n"

namespace = {"__name__": "hosted_preview_runtime"}
exec(compile(stripped, str(source_path), "exec"), namespace)

html = namespace["HTML"]
html = html.replace(
    '<button class="btn" onclick="sendMsg(',
    '<button class="btn" style="min-width:140px" onclick="sendMsg('
)
html = html.replace('">Send</button>', '">Send message</button>')
html = html.replace(
    'alert("Interview proposed")',
    'document.getElementById("nav-worker").textContent="Worker • interview waiting";alert("Interview proposed. Switch to Worker and accept it to confirm the meeting.")'
)
html = html.replace(
    '<button class="btn gold" onclick="submitCustomer()">Find someone to help</button>',
    '<button id="customer-submit" class="btn gold" onclick="submitCustomer()">Find someone to help</button>'
)
html = html.replace(
    'async function submitCustomer(){const b=await api(',
    'async function submitCustomer(){const btn=document.getElementById("customer-submit");btn.disabled=true;btn.textContent="Request sent";const b=await api('
)
namespace["HTML"] = html

app = namespace["app"]
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
PERSISTED = {
    "intros": namespace["INTROS"],
    "conversations": namespace["CONVERSATIONS"],
    "messages": namespace["MESSAGES"],
    "meetings": namespace["MEETINGS"],
    "customer_requests": namespace["CUSTOMER_REQUESTS"],
}

def _connect():
    return psycopg.connect(DATABASE_URL, connect_timeout=8)

def _ensure_schema():
    if not DATABASE_URL:
        return
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS trade_network_pilot_state (
                    id smallint PRIMARY KEY DEFAULT 1 CHECK (id = 1),
                    payload jsonb NOT NULL DEFAULT '{}'::jsonb,
                    updated_at timestamptz NOT NULL DEFAULT now()
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS trade_network_pilot_events (
                    id bigserial PRIMARY KEY,
                    occurred_at timestamptz NOT NULL DEFAULT now(),
                    method text NOT NULL,
                    path text NOT NULL,
                    actor text,
                    status_code integer NOT NULL
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS trade_network_pilot_durability (
                    id smallint PRIMARY KEY DEFAULT 1 CHECK (id = 1),
                    marker text NOT NULL,
                    restart_count integer NOT NULL DEFAULT 0,
                    first_seen_at timestamptz NOT NULL DEFAULT now(),
                    last_seen_at timestamptz NOT NULL DEFAULT now()
                )
            """)
        conn.commit()

def _touch_durability_marker():
    if not DATABASE_URL:
        return None
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO trade_network_pilot_durability (id, marker, restart_count, first_seen_at, last_seen_at)
                VALUES (1, 'FICTIONAL_R3_DURABILITY_SENTINEL', 1, now(), now())
                ON CONFLICT (id) DO UPDATE
                SET restart_count = trade_network_pilot_durability.restart_count + 1,
                    last_seen_at = now()
                RETURNING restart_count, first_seen_at, last_seen_at
            """)
            row = cur.fetchone()
        conn.commit()
    return row

def _load_state():
    if not DATABASE_URL:
        return
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT payload FROM trade_network_pilot_state WHERE id = 1")
            row = cur.fetchone()
    if not row:
        return
    payload = row[0] or {}
    for key, target in PERSISTED.items():
        target.clear()
        target.extend(payload.get(key, []))

def _snapshot():
    return {key: list(value) for key, value in PERSISTED.items()}

def _actor_from_request(request):
    auth = request.headers.get("authorization", "")
    if not auth.startswith("Bearer "):
        return None
    token = auth.split(" ", 1)[1]
    user = namespace["TOKENS"].get(token)
    return user["username"] if user else None

def _save_state(request, status_code):
    if not DATABASE_URL:
        return
    payload = json.dumps(_snapshot())
    actor = _actor_from_request(request)
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO trade_network_pilot_state (id, payload, updated_at)
                VALUES (1, %s::jsonb, now())
                ON CONFLICT (id) DO UPDATE
                SET payload = EXCLUDED.payload, updated_at = now()
            """, (payload,))
            cur.execute("""
                INSERT INTO trade_network_pilot_events (method, path, actor, status_code)
                VALUES (%s, %s, %s, %s)
            """, (request.method, request.url.path, actor, status_code))
        conn.commit()


def _run_house_selftest():
    ns = namespace
    saved = {
        "tokens": dict(ns["TOKENS"]),
        "intros": list(ns["INTROS"]),
        "conversations": list(ns["CONVERSATIONS"]),
        "messages": list(ns["MESSAGES"]),
        "meetings": list(ns["MEETINGS"]),
        "customer_requests": list(ns["CUSTOMER_REQUESTS"]),
    }
    try:
        ns["TOKENS"].clear()
        ns["INTROS"].clear()
        ns["CONVERSATIONS"].clear()
        ns["MESSAGES"].clear()
        ns["MEETINGS"].clear()
        ns["CUSTOMER_REQUESTS"].clear()

        expires = ns["time"].time() + 3600
        ns["TOKENS"].update({
            "t-worker": {"username":"jordan", **ns["USERS"]["jordan"], "expires_at": expires},
            "t-owner": {"username":"owner", **ns["USERS"]["owner"], "expires_at": expires},
            "t-owner2": {"username":"owner2", **ns["USERS"]["owner2"], "expires_at": expires},
            "t-customer": {"username":"customer", **ns["USERS"]["customer"], "expires_at": expires},
            "t-admin": {"username":"admin", **ns["USERS"]["admin"], "expires_at": expires},
        })

        failures = []

        try:
            ns["auth_header"]("Bearer invalid")
            failures.append("invalid_session_not_rejected")
        except Exception as exc:
            if getattr(exc, "status_code", None) != 401:
                failures.append("invalid_session_wrong_status")

        intro1 = ns["create_intro"](ns["IntroBody"](opportunity_id="n2"), "Bearer t-worker")
        intro2 = ns["create_intro"](ns["IntroBody"](opportunity_id="n2"), "Bearer t-worker")
        if intro1["id"] != intro2["id"] or len(ns["INTROS"]) != 1:
            failures.append("duplicate_intro")

        if ns["partner_intros"]("Bearer t-owner2")["items"]:
            failures.append("employer_isolation_list")
        try:
            ns["accept_intro"](intro1["id"], "Bearer t-owner2")
            failures.append("employer_isolation_accept")
        except Exception as exc:
            if getattr(exc, "status_code", None) != 404:
                failures.append("employer_isolation_accept_status")

        accepted = ns["accept_intro"](intro1["id"], "Bearer t-owner")
        conv = accepted["conversation"]

        meeting_body = ns["MeetingBody"](
            conversation_id=conv["id"],
            start_at="Fictional Tomorrow 10:00 AM",
            end_at="Fictional Tomorrow 10:30 AM",
        )
        meet1 = ns["create_meeting"](meeting_body, "Bearer t-owner")
        meet2 = ns["create_meeting"](meeting_body, "Bearer t-owner")
        if meet1["id"] != meet2["id"] or len(ns["MEETINGS"]) != 1:
            failures.append("duplicate_meeting")

        customer_body = ns["CustomerBody"](
            service_category="HVAC",
            description="Fictional duplicate guard",
            location_text="Oklahoma City",
            urgency="THIS_WEEK",
            learner_preference="NO_PREFERENCE",
        )
        req1 = ns["customer_request"](customer_body, "Bearer t-customer")
        req2 = ns["customer_request"](customer_body, "Bearer t-customer")
        if req1["id"] != req2["id"] or len(ns["CUSTOMER_REQUESTS"]) != 1:
            failures.append("duplicate_customer")

        try:
            ns["send_message"](conv["id"], ns["MessageBody"](body="   "), "Bearer t-worker")
            failures.append("blank_message_not_rejected")
        except Exception as exc:
            if getattr(exc, "status_code", None) != 422:
                failures.append("blank_message_wrong_status")

        if ns["control_tower"]("Bearer t-admin")["decision_state"] != "UNKNOWN":
            failures.append("admin_truth_state")

        ns["TOKENS"]["t-expired"] = {"username":"jordan", **ns["USERS"]["jordan"], "expires_at": 0}
        try:
            ns["auth_header"]("Bearer t-expired")
            failures.append("expired_session_not_rejected")
        except Exception as exc:
            if getattr(exc, "status_code", None) != 401:
                failures.append("expired_session_wrong_status")

        ns["logout"]("Bearer t-worker")
        try:
            ns["auth_header"]("Bearer t-worker")
            failures.append("revoked_session_not_rejected")
        except Exception as exc:
            if getattr(exc, "status_code", None) != 401:
                failures.append("revoked_session_wrong_status")

        if failures:
            print("HOUSE_SELFTEST FAIL", ",".join(failures))
            return False
        print("HOUSE_SELFTEST PASS checks=9")
        return True
    finally:
        ns["TOKENS"].clear()
        ns["TOKENS"].update(saved["tokens"])
        for key, source in (
            ("INTROS", saved["intros"]),
            ("CONVERSATIONS", saved["conversations"]),
            ("MESSAGES", saved["messages"]),
            ("MEETINGS", saved["meetings"]),
            ("CUSTOMER_REQUESTS", saved["customer_requests"]),
        ):
            ns[key].clear()
            ns[key].extend(source)

def _run_persistence_roundtrip():
    if not DATABASE_URL:
        return None
    original = _snapshot()
    marker = {
        "id": "roundtrip-fictional",
        "worker": "fictional-selftest",
        "worker_name": "Fictional Selftest",
        "opportunity_id": "n2",
        "opportunity_title": "HVAC Trainee",
        "employer": "owner",
        "state": "PENDING",
        "created_at": "SELFTEST",
    }
    try:
        namespace["INTROS"].append(marker)
        payload = json.dumps(_snapshot())
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO trade_network_pilot_state (id, payload, updated_at)
                    VALUES (1, %s::jsonb, now())
                    ON CONFLICT (id) DO UPDATE
                    SET payload = EXCLUDED.payload, updated_at = now()
                """, (payload,))
            conn.commit()

        for target in PERSISTED.values():
            target.clear()
        _load_state()
        seen = any(x.get("id") == "roundtrip-fictional" for x in namespace["INTROS"])
        if not seen:
            raise RuntimeError("fictional roundtrip marker not restored")
        print("PERSISTENCE_ROUNDTRIP PASS")
        return True
    finally:
        for key, target in PERSISTED.items():
            target.clear()
            target.extend(original.get(key, []))
        payload = json.dumps(original)
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO trade_network_pilot_state (id, payload, updated_at)
                    VALUES (1, %s::jsonb, now())
                    ON CONFLICT (id) DO UPDATE
                    SET payload = EXCLUDED.payload, updated_at = now()
                """, (payload,))
            conn.commit()

HOUSE_SELFTEST_READY = _run_house_selftest()

PERSISTENCE_READY = False
PERSISTENCE_ERROR = None
if DATABASE_URL:
    try:
        _ensure_schema()
        _load_state()
        _run_persistence_roundtrip()
        durability = _touch_durability_marker()
        if durability:
            print("PERSISTENCE_DURABILITY", f"restart_count={durability[0]}")
        PERSISTENCE_READY = True
    except Exception as exc:
        PERSISTENCE_ERROR = f"{type(exc).__name__}: {exc}"
        print("PERSISTENCE_INIT_ERROR", PERSISTENCE_ERROR)

@app.middleware("http")
async def persist_successful_writes(request, call_next):
    response = await call_next(request)
    if DATABASE_URL and request.method in {"POST", "PUT", "PATCH", "DELETE"} and response.status_code < 400:
        try:
            _save_state(request, response.status_code)
            response.headers["X-Trade-Network-Persistence"] = "saved"
        except Exception as exc:
            print("PERSISTENCE_WRITE_ERROR", type(exc).__name__, str(exc))
            response.headers["X-Trade-Network-Persistence"] = "error"
    return response

def _persistence_details():
    if not DATABASE_URL:
        return {
            "enabled": False,
            "ready": False,
            "mode": "memory-only",
            "updated_at": None,
            "event_count": None,
            "restart_count": None,
            "first_seen_at": None,
            "last_seen_at": None,
            "house_selftest_ready": HOUSE_SELFTEST_READY,
            "error": None,
        }
    updated_at = None
    event_count = None
    durability_row = None
    try:
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT updated_at FROM trade_network_pilot_state WHERE id = 1")
                row = cur.fetchone()
                updated_at = row[0].isoformat() if row and row[0] else None
                cur.execute("SELECT count(*) FROM trade_network_pilot_events")
                event_count = cur.fetchone()[0]
                cur.execute("SELECT restart_count, first_seen_at, last_seen_at FROM trade_network_pilot_durability WHERE id = 1")
                durability_row = cur.fetchone()
    except Exception as exc:
        return {
            "enabled": True,
            "ready": False,
            "mode": "postgres",
            "updated_at": None,
            "event_count": None,
            "restart_count": None,
            "first_seen_at": None,
            "last_seen_at": None,
            "house_selftest_ready": HOUSE_SELFTEST_READY,
            "error": f"{type(exc).__name__}: {exc}",
        }
    return {
        "enabled": True,
        "ready": PERSISTENCE_READY,
        "mode": "postgres",
        "updated_at": updated_at,
        "event_count": event_count,
        "restart_count": durability_row[0] if durability_row else None,
        "first_seen_at": durability_row[1].isoformat() if durability_row and durability_row[1] else None,
        "last_seen_at": durability_row[2].isoformat() if durability_row and durability_row[2] else None,
        "house_selftest_ready": HOUSE_SELFTEST_READY,
        "error": PERSISTENCE_ERROR,
    }

@app.get("/api/persistence")
def persistence_status():
    details = _persistence_details()
    return {
        "enabled": details["enabled"],
        "ready": details["ready"],
        "mode": details["mode"],
        "house_selftest_ready": details["house_selftest_ready"],
        "status": "READY" if details["ready"] else ("MEMORY_ONLY" if not details["enabled"] else "UNAVAILABLE"),
    }

@app.get("/api/admin/persistence")
def admin_persistence_status(authorization: str | None = namespace["Header"](None)):
    user = namespace["auth_header"](authorization)
    namespace["require_role"](user, "ADMIN")
    return _persistence_details()
