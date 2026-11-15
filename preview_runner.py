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

PERSISTENCE_READY = False
PERSISTENCE_ERROR = None
if DATABASE_URL:
    try:
        _ensure_schema()
        _load_state()
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

@app.get("/api/persistence")
def persistence_status():
    if not DATABASE_URL:
        return JSONResponse({
            "enabled": False,
            "ready": False,
            "mode": "memory-only",
            "error": None
        })
    updated_at = None
    event_count = None
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
        return JSONResponse({
            "enabled": True,
            "ready": False,
            "mode": "postgres",
            "error": f"{type(exc).__name__}: {exc}"
        }, status_code=503)
    return {
        "enabled": True,
        "ready": PERSISTENCE_READY,
        "mode": "postgres",
        "updated_at": updated_at,
        "event_count": event_count,
        "restart_count": durability_row[0] if durability_row else None,
        "first_seen_at": durability_row[1].isoformat() if durability_row and durability_row[1] else None,
        "last_seen_at": durability_row[2].isoformat() if durability_row and durability_row[2] else None,
        "error": PERSISTENCE_ERROR
    }
