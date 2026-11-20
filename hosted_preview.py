from fastapi import FastAPI, HTTPException, Header
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Optional
import secrets
import time
from datetime import datetime, timezone

app = FastAPI(title="Trade Network Hosted Preview R2")

USERS = {
    "jordan": {"password": "TradeDemo123!", "role": "WORKER", "name": "Jordan Carter"},
    "owner": {"password": "TradeDemo123!", "role": "EMPLOYER", "name": "Red River Mechanical"},
    "owner2": {"password": "TradeDemo123!", "role": "EMPLOYER", "name": "Fictional Second Employer"},
    "customer": {"password": "TradeDemo123!", "role": "CUSTOMER", "name": "Demo Customer"},
    "admin": {"password": "TradeDemo123!", "role": "ADMIN", "name": "Demo Administrator"},
}
TOKENS = {}
SESSION_TTL_SECONDS = 7200
OPPORTUNITIES = [
    {"id":"n2","title":"HVAC Trainee","employer":"Red River Mechanical","pay":"Training wage","status":"OPEN NOW","will_train":True,"last_confirmed":"Today","fit":"Best Career Move","location":"Oklahoma City"},
    {"id":"n1","title":"Warehouse Helper","employer":"Red River Mechanical","pay":"$18/hr reported","status":"OPEN NOW","will_train":False,"last_confirmed":"Today","fit":"Fastest Money Move","location":"Oklahoma City"},
]
INTROS = []
CONVERSATIONS = []
MESSAGES = []
MEETINGS = []
CUSTOMER_REQUESTS = []
HELP_REQUESTS = []

def now():
    return datetime.now(timezone.utc).isoformat()

def auth_header(authorization: Optional[str]):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "authentication required")
    token = authorization.split(" ", 1)[1]
    user = TOKENS.get(token)
    if not user:
        raise HTTPException(401, "invalid session")
    expires_at = user.get("expires_at")
    if expires_at is not None and expires_at <= time.time():
        TOKENS.pop(token, None)
        raise HTTPException(401, "session expired")
    return user

def require_role(user, role):
    if user["role"] != role:
        raise HTTPException(403, f"role denied: {role}")

def _worker_next_action(username):
    waiting_help = next((x for x in reversed(HELP_REQUESTS) if x["worker"] == username and x["state"] == "WAITING_ON_WORKER"), None)
    if waiting_help:
        return {
            "code": "RESPOND_TO_HELP_REQUEST",
            "title": "Reply to your support coordinator",
            "detail": "Your support request needs one more detail. Reply below so it can return to the review queue.",
            "stage": "SUPPORT_FOLLOWUP",
        }

    worker_intros = [x for x in INTROS if x["worker"] == username]
    if not worker_intros:
        return {
            "code": "REQUEST_INTRO",
            "title": "Request an introduction",
            "detail": "Pick the opportunity that best matches what you need next.",
            "stage": "DISCOVER",
        }

    accepted = [x for x in worker_intros if x["state"] == "ACCEPTED"]
    if not accepted:
        return {
            "code": "WAIT_FOR_EMPLOYER",
            "title": "Employer review in progress",
            "detail": "Your introduction is waiting on the employer. You do not need to submit it again.",
            "stage": "INTRO_PENDING",
        }

    conv_ids = {c["id"] for c in CONVERSATIONS if c["worker"] == username}
    worker_meetings = [m for m in MEETINGS if m["conversation_id"] in conv_ids]
    proposed = [m for m in worker_meetings if m["state"] == "PROPOSED"]
    if proposed:
        return {
            "code": "ACCEPT_INTERVIEW",
            "title": "Accept your interview",
            "detail": f"{proposed[0]['start_at']} is waiting for your confirmation.",
            "stage": "MEETING_PROPOSED",
        }

    confirmed = [m for m in worker_meetings if m["state"] == "CONFIRMED"]
    if confirmed:
        return {
            "code": "PREPARE_INTERVIEW",
            "title": "Prepare for your confirmed interview",
            "detail": f"Interview confirmed for {confirmed[0]['start_at']}.",
            "stage": "MEETING_CONFIRMED",
        }

    worker_messages = [m for m in MESSAGES if m["conversation_id"] in conv_ids and m["sender"] == username]
    if not worker_messages:
        return {
            "code": "SEND_FIRST_MESSAGE",
            "title": "Send your first message",
            "detail": "Your introduction was accepted. Start the conversation with the employer.",
            "stage": "CONVERSATION_OPEN",
        }

    return {
        "code": "WAIT_FOR_INTERVIEW",
        "title": "Keep the conversation moving",
        "detail": "You have contacted the employer. Watch for an interview proposal or reply.",
        "stage": "CONVERSATION_ACTIVE",
    }

def _employer_next_action(username):
    pending = [x for x in INTROS if x["employer"] == username and x["state"] == "PENDING"]
    if pending:
        return {
            "code": "REVIEW_INTRO",
            "title": "Review a worker introduction",
            "detail": f"{pending[0]['worker_name']} is waiting for your decision.",
            "stage": "INTRO_PENDING",
        }

    conv_ids = {c["id"] for c in CONVERSATIONS if c["employer"] == username}
    if not conv_ids:
        return {
            "code": "WAIT_FOR_INTRO",
            "title": "No worker action needed right now",
            "detail": "New worker introductions will appear here when they are requested.",
            "stage": "IDLE",
        }

    employer_meetings = [m for m in MEETINGS if m["conversation_id"] in conv_ids]
    if any(m["state"] == "CONFIRMED" for m in employer_meetings):
        m = next(m for m in employer_meetings if m["state"] == "CONFIRMED")
        return {
            "code": "PREPARE_INTERVIEW",
            "title": "Prepare for the confirmed interview",
            "detail": f"Interview confirmed for {m['start_at']}.",
            "stage": "MEETING_CONFIRMED",
        }

    if any(m["state"] == "PROPOSED" for m in employer_meetings):
        return {
            "code": "WAIT_FOR_WORKER_CONFIRMATION",
            "title": "Interview proposal sent",
            "detail": "The worker still needs to accept the interview time.",
            "stage": "MEETING_PROPOSED",
        }

    employer_messages = [m for m in MESSAGES if m["conversation_id"] in conv_ids and m["sender"] == username]
    if not employer_messages:
        return {
            "code": "SEND_FIRST_MESSAGE",
            "title": "Message the worker",
            "detail": "The introduction is accepted. Start the conversation before proposing an interview.",
            "stage": "CONVERSATION_OPEN",
        }

    return {
        "code": "PROPOSE_INTERVIEW",
        "title": "Propose an interview",
        "detail": "The conversation is active. Move the worker to a real next step.",
        "stage": "CONVERSATION_ACTIVE",
    }

@app.get("/api/next-action")
def next_action(authorization: Optional[str] = Header(None)):
    u = auth_header(authorization)
    if u["role"] == "WORKER":
        return _worker_next_action(u["username"])
    if u["role"] == "EMPLOYER":
        return _employer_next_action(u["username"])
    raise HTTPException(403, "next action not available for role")

def _worker_journey_receipt(username):
    next_state = _worker_next_action(username)
    worker_intros = [x for x in INTROS if x["worker"] == username]
    conv_ids = {c["id"] for c in CONVERSATIONS if c["worker"] == username}
    worker_messages = [m for m in MESSAGES if m["conversation_id"] in conv_ids and m["sender"] == username]
    worker_meetings = [m for m in MEETINGS if m["conversation_id"] in conv_ids]

    events = []
    for intro in worker_intros:
        events.append({
            "event_type": "INTRO_REQUESTED",
            "state": intro["state"],
            "reference": intro["id"],
            "recorded_at": intro.get("created_at"),
            "truth_state": "SUPPORTED",
        })
        if intro["state"] == "ACCEPTED":
            events.append({
                "event_type": "INTRO_ACCEPTED",
                "state": "ACCEPTED",
                "reference": intro["id"],
                "recorded_at": intro.get("created_at"),
                "truth_state": "SUPPORTED",
            })

    for message in worker_messages:
        events.append({
            "event_type": "WORKER_MESSAGE_SENT",
            "state": "RECORDED",
            "reference": message["id"],
            "recorded_at": message.get("created_at"),
            "truth_state": "SUPPORTED",
        })

    for meeting in worker_meetings:
        events.append({
            "event_type": "INTERVIEW_" + meeting["state"],
            "state": meeting["state"],
            "reference": meeting["id"],
            "recorded_at": meeting.get("start_at"),
            "truth_state": "SUPPORTED",
        })

    return {
        "receipt_type": "CAREER_JOURNEY_ACTIVITY",
        "worker_id": username,
        "generated_at": now(),
        "current_stage": next_state["stage"],
        "next_action_code": next_state["code"],
        "events": events,
        "evidence_scope": "PLATFORM_RECORDED_ACTIVITY_ONLY",
        "authority_state": "UNKNOWN",
        "qualifying_hours_authority": "NONE",
        "credential_acceptance_authority": "NONE",
        "disclaimer": "This receipt records fictional pilot activity inside Trade Network. It is not a credential, license, qualifying-hours decision, employment verification, or regulator acceptance.",
    }

@app.get("/api/worker/journey-receipt")
def worker_journey_receipt(authorization: Optional[str] = Header(None)):
    u = auth_header(authorization)
    require_role(u, "WORKER")
    return _worker_journey_receipt(u["username"])

class LoginBody(BaseModel):
    identifier: str
    password: str

class IntroBody(BaseModel):
    opportunity_id: str

class MessageBody(BaseModel):
    body: str

class MeetingBody(BaseModel):
    conversation_id: str
    start_at: str = "Tomorrow 10:00 AM"
    end_at: str = "Tomorrow 10:30 AM"

class CustomerBody(BaseModel):
    service_category: str = "HVAC"
    description: str = ""
    location_text: str = "Oklahoma City"
    urgency: str = "THIS_WEEK"
    learner_preference: str = "NO_PREFERENCE"

class WorkerHelpBody(BaseModel):
    blocker: str
    details: str = ""
    urgency: str = "THIS_WEEK"

class WorkerHelpReviewBody(BaseModel):
    state: str
    worker_visible_update: str = ""

class WorkerHelpResponseBody(BaseModel):
    message: str

@app.get("/health")
def health():
    return {"ok": True, "service":"trade-network-r2-preview"}

@app.post("/api/login")
def login(body: LoginBody):
    key = body.identifier.strip().lower()
    u = USERS.get(key)
    if not u or body.password != u["password"]:
        raise HTTPException(401, "invalid credentials")
    token = secrets.token_urlsafe(24)
    expires_at = time.time() + SESSION_TTL_SECONDS
    TOKENS[token] = {"username":key, **u, "expires_at":expires_at}
    return {"session_token":token,"user_id":key,"roles":[u["role"]],"name":u["name"],"expires_in":SESSION_TTL_SECONDS}

@app.post("/api/logout")
def logout(authorization: Optional[str] = Header(None)):
    u = auth_header(authorization)
    token = authorization.split(" ", 1)[1]
    TOKENS.pop(token, None)
    return {"ok": True, "user_id": u["username"]}

@app.get("/api/me")
def me(authorization: Optional[str] = Header(None)):
    u = auth_header(authorization)
    return {"user_id":u["username"],"roles":[u["role"]],"name":u["name"]}

@app.get("/api/opportunities")
def opportunities(authorization: Optional[str] = Header(None)):
    u = auth_header(authorization)
    require_role(u, "WORKER")
    return {"items":OPPORTUNITIES,"truth_state":"DEMO"}

@app.post("/api/intros")
def create_intro(body: IntroBody, authorization: Optional[str] = Header(None)):
    u = auth_header(authorization)
    require_role(u, "WORKER")
    opp = next((x for x in OPPORTUNITIES if x["id"] == body.opportunity_id), None)
    if not opp:
        raise HTTPException(404, "opportunity not found")
    existing = next((x for x in INTROS if x["worker"]==u["username"] and x["opportunity_id"]==body.opportunity_id and x["state"] in ("PENDING","ACCEPTED")), None)
    if existing:
        return existing
    item = {"id":f"intro-{len(INTROS)+1}","worker":u["username"],"worker_name":u["name"],"opportunity_id":opp["id"],"opportunity_title":opp["title"],"employer":"owner","state":"PENDING","created_at":now()}
    INTROS.append(item)
    return item

@app.get("/api/partner/intros")
def partner_intros(authorization: Optional[str] = Header(None)):
    u = auth_header(authorization)
    require_role(u, "EMPLOYER")
    return {"items":[x for x in INTROS if x["employer"]==u["username"]]}

@app.post("/api/partner/intros/{intro_id}/accept")
def accept_intro(intro_id: str, authorization: Optional[str] = Header(None)):
    u = auth_header(authorization)
    require_role(u, "EMPLOYER")
    intro = next((x for x in INTROS if x["id"]==intro_id and x["employer"]==u["username"]), None)
    if not intro:
        raise HTTPException(404, "intro not found")
    intro["state"] = "ACCEPTED"
    conv = next((c for c in CONVERSATIONS if c["intro_id"]==intro_id), None)
    if not conv:
        conv = {"id":f"conv-{len(CONVERSATIONS)+1}","intro_id":intro_id,"worker":intro["worker"],"employer":u["username"],"state":"OPEN"}
        CONVERSATIONS.append(conv)
    return {"intro":intro,"conversation":conv}

@app.get("/api/conversations")
def conversations(authorization: Optional[str] = Header(None)):
    u = auth_header(authorization)
    items = [c for c in CONVERSATIONS if u["username"] in (c["worker"],c["employer"])]
    return {"items":items}

@app.get("/api/conversations/{conversation_id}/messages")
def get_messages(conversation_id: str, authorization: Optional[str] = Header(None)):
    u = auth_header(authorization)
    c = next((x for x in CONVERSATIONS if x["id"]==conversation_id), None)
    if not c or u["username"] not in (c["worker"],c["employer"]):
        raise HTTPException(403, "conversation access denied")
    return {"items":[m for m in MESSAGES if m["conversation_id"]==conversation_id]}

@app.post("/api/conversations/{conversation_id}/messages")
def send_message(conversation_id: str, body: MessageBody, authorization: Optional[str] = Header(None)):
    u = auth_header(authorization)
    clean_body = body.body.strip()
    if not clean_body:
        raise HTTPException(422, "message body required")
    c = next((x for x in CONVERSATIONS if x["id"]==conversation_id), None)
    if not c or u["username"] not in (c["worker"],c["employer"]):
        raise HTTPException(403, "conversation access denied")
    m = {"id":f"msg-{len(MESSAGES)+1}","conversation_id":conversation_id,"sender":u["username"],"sender_name":u["name"],"body":clean_body,"created_at":now()}
    MESSAGES.append(m)
    return m

@app.post("/api/meetings")
def create_meeting(body: MeetingBody, authorization: Optional[str] = Header(None)):
    u = auth_header(authorization)
    c = next((x for x in CONVERSATIONS if x["id"]==body.conversation_id), None)
    if not c or u["username"] not in (c["worker"],c["employer"]):
        raise HTTPException(403, "conversation access denied")
    existing = next((m for m in MEETINGS
                     if m["conversation_id"] == c["id"]
                     and m["start_at"] == body.start_at
                     and m["end_at"] == body.end_at
                     and m["state"] in ("PROPOSED", "CONFIRMED")), None)
    if existing:
        return existing
    mt = {"id":f"meet-{len(MEETINGS)+1}","conversation_id":c["id"],"start_at":body.start_at,"end_at":body.end_at,"state":"PROPOSED","created_by":u["username"],"accepted_by":[]}
    MEETINGS.append(mt)
    return mt

@app.get("/api/meetings")
def list_meetings(authorization: Optional[str] = Header(None)):
    u = auth_header(authorization)
    conv_ids = {c["id"] for c in CONVERSATIONS if u["username"] in (c["worker"],c["employer"])}
    return {"items":[m for m in MEETINGS if m["conversation_id"] in conv_ids]}

@app.post("/api/meetings/{meeting_id}/accept")
def accept_meeting(meeting_id: str, authorization: Optional[str] = Header(None)):
    u = auth_header(authorization)
    m = next((x for x in MEETINGS if x["id"]==meeting_id), None)
    if not m:
        raise HTTPException(404, "meeting not found")
    c = next((x for x in CONVERSATIONS if x["id"]==m["conversation_id"]), None)
    if not c or u["username"] not in (c["worker"],c["employer"]):
        raise HTTPException(403, "meeting access denied")
    if u["username"] not in m["accepted_by"]:
        m["accepted_by"].append(u["username"])
    participants = {c["worker"],c["employer"]}
    if participants.issubset(set(m["accepted_by"] + [m["created_by"]])):
        m["state"] = "CONFIRMED"
    return m

@app.post("/api/customer/requests")
def customer_request(body: CustomerBody, authorization: Optional[str] = Header(None)):
    u = auth_header(authorization)
    require_role(u, "CUSTOMER")
    existing = next((x for x in CUSTOMER_REQUESTS
                     if x["customer"] == u["username"]
                     and x["service_category"] == body.service_category
                     and x["description"] == body.description
                     and x["location_text"] == body.location_text
                     and x["urgency"] == body.urgency
                     and x["learner_preference"] == body.learner_preference
                     and x["state"] == "MATCHED"), None)
    if existing:
        return existing
    item = {"id":f"req-{len(CUSTOMER_REQUESTS)+1}","customer":u["username"],**body.model_dump(),"state":"MATCHED","matched_business":"Red River Mechanical","truth_state":"DEMO","created_at":now()}
    CUSTOMER_REQUESTS.append(item)
    return item

HELP_BLOCKERS = {
    "TRANSPORT", "CHILDCARE", "TOOLS", "LICENSING",
    "SCHEDULE", "LOCATION", "TRAINING", "EMPLOYER_RESPONSE", "OTHER",
}
HELP_URGENCIES = {"IMMEDIATELY", "THIS_WEEK", "EXPLORING"}

@app.post("/api/worker/help-requests")
def create_worker_help_request(body: WorkerHelpBody, authorization: Optional[str] = Header(None)):
    u = auth_header(authorization)
    require_role(u, "WORKER")
    blocker = body.blocker.strip().upper()
    details = body.details.strip()
    urgency = body.urgency.strip().upper()
    if blocker not in HELP_BLOCKERS:
        raise HTTPException(422, "unsupported blocker category")
    if urgency not in HELP_URGENCIES:
        raise HTTPException(422, "unsupported urgency")
    if len(details) > 1000:
        raise HTTPException(422, "details must be 1000 characters or fewer")
    existing = next((
        x for x in HELP_REQUESTS
        if x["worker"] == u["username"]
        and x["blocker"] == blocker
        and x["details"] == details
        and x["urgency"] == urgency
        and x["state"] in ("OPEN", "IN_REVIEW", "WAITING_ON_WORKER")
    ), None)
    if existing:
        return existing
    item = {
        "id": f"help-{len(HELP_REQUESTS) + 1}",
        "worker": u["username"],
        "worker_name": u["name"],
        "blocker": blocker,
        "details": details,
        "urgency": urgency,
        "state": "OPEN",
        "created_at": now(),
        "truth_state": "SUPPORTED",
        "evidence_scope": "PLATFORM_RECORDED_REQUEST_ONLY",
        "resolution_authority": "NONE",
        "notice": "Request recorded only. No resource, employer, or service provider has been confirmed or contacted.",
    }
    HELP_REQUESTS.append(item)
    return item

@app.get("/api/worker/help-requests")
def list_worker_help_requests(authorization: Optional[str] = Header(None)):
    u = auth_header(authorization)
    require_role(u, "WORKER")
    return {"items": [x for x in HELP_REQUESTS if x["worker"] == u["username"]]}

@app.post("/api/worker/help-requests/{request_id}/close")
def close_worker_help_request(request_id: str, authorization: Optional[str] = Header(None)):
    u = auth_header(authorization)
    require_role(u, "WORKER")
    item = next((x for x in HELP_REQUESTS if x["id"] == request_id and x["worker"] == u["username"]), None)
    if not item:
        raise HTTPException(404, "help request not found")
    if item["state"] != "CLOSED_BY_WORKER":
        item["state"] = "CLOSED_BY_WORKER"
        item["closed_at"] = now()
        item["updated_at"] = now()
    return item

@app.post("/api/worker/help-requests/{request_id}/respond")
def respond_worker_help_request(request_id: str, body: WorkerHelpResponseBody, authorization: Optional[str] = Header(None)):
    u = auth_header(authorization)
    require_role(u, "WORKER")
    item = next((x for x in HELP_REQUESTS if x["id"] == request_id and x["worker"] == u["username"]), None)
    if not item:
        raise HTTPException(404, "help request not found")
    if item["state"] != "WAITING_ON_WORKER":
        raise HTTPException(409, "request is not waiting for a worker response")
    message = body.message.strip()
    if not message or len(message) > 500:
        raise HTTPException(422, "reply must contain 1 to 500 characters")
    responses = item.setdefault("worker_responses", [])
    responses.append({
        "message": message,
        "responded_by": u["username"],
        "responded_at": now(),
        "truth_state": "SUPPORTED",
    })
    item["state"] = "OPEN"
    item["worker_visible_update"] = "Your reply was recorded. The request is back in the review queue."
    item["updated_at"] = now()
    item["last_worker_response_at"] = item["updated_at"]
    item["resolution_authority"] = "NONE"
    return item

@app.get("/api/admin/help-requests")
def admin_help_requests(authorization: Optional[str] = Header(None)):
    u = auth_header(authorization)
    require_role(u, "ADMIN")
    return {"items": list(HELP_REQUESTS), "truth_state": "SUPPORTED_PLATFORM_ACTIVITY_ONLY"}

@app.patch("/api/admin/help-requests/{request_id}")
def review_worker_help_request(request_id: str, body: WorkerHelpReviewBody, authorization: Optional[str] = Header(None)):
    u = auth_header(authorization)
    require_role(u, "ADMIN")
    item = next((x for x in HELP_REQUESTS if x["id"] == request_id), None)
    if not item:
        raise HTTPException(404, "help request not found")
    if item["state"] == "CLOSED_BY_WORKER":
        raise HTTPException(409, "worker-closed request cannot be reopened in this pilot")
    state = body.state.strip().upper()
    if state not in {"OPEN", "IN_REVIEW", "WAITING_ON_WORKER"}:
        raise HTTPException(422, "unsupported review state; this pilot cannot mark a request resolved")
    update = body.worker_visible_update.strip()
    if len(update) > 500:
        raise HTTPException(422, "worker update must be 500 characters or fewer")
    if state == "WAITING_ON_WORKER" and not update:
        raise HTTPException(422, "a worker-visible update is required")
    item["state"] = state
    item["reviewed_by"] = u["username"]
    item["worker_visible_update"] = update
    item["updated_at"] = now()
    item["resolution_authority"] = "NONE"
    return item

@app.get("/api/admin/control-tower")
def control_tower(authorization: Optional[str] = Header(None)):
    u = auth_header(authorization)
    require_role(u, "ADMIN")
    return {
        "decision_state":"UNKNOWN",
        "truth_state":"DEMO",
        "counts":{
            "introductions":len(INTROS),
            "accepted_introductions":len([x for x in INTROS if x["state"]=="ACCEPTED"]),
            "conversations":len(CONVERSATIONS),
            "messages":len(MESSAGES),
            "meetings":len(MEETINGS),
            "confirmed_meetings":len([x for x in MEETINGS if x["state"]=="CONFIRMED"]),
            "customer_requests":len(CUSTOMER_REQUESTS),
            "worker_help_requests":len(HELP_REQUESTS),
            "open_worker_help_requests":len([x for x in HELP_REQUESTS if x["state"] == "OPEN"]),
        }
    }

HTML = r"""<!doctype html>
<html>
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Trade Network R2 Preview</title>
<style>
:root{--bg:#f7f5f0;--ink:#1c1917;--panel:#fff;--line:#e7e2d9;--gold:#d49b2a;--green:#2f7d5b;--blue:#2563a6;--red:#b84a4a;--muted:#716b63}
*{box-sizing:border-box}body{margin:0;font-family:Segoe UI,system-ui,sans-serif;background:var(--bg);color:var(--ink);font-size:17px}
header{background:#1c1917;color:#fff;padding:18px 28px;display:flex;align-items:center;gap:14px;position:sticky;top:0;z-index:5}
.logo{width:38px;height:38px;border-radius:10px;background:#2b2825;display:grid;place-items:center;color:#f0b84b;font-weight:800;font-size:21px}
header h1{font-size:21px;margin:0}.tag{color:#cfc8bd;font-size:13px}.wrap{max-width:1180px;margin:auto;padding:28px}
.notice{border:1px solid #ead19b;background:#fff8e8;border-radius:14px;padding:12px 16px;color:#6b4d13;margin-bottom:20px;font-size:14px}
.grid{display:grid;grid-template-columns:260px 1fr;gap:22px}.card{background:var(--panel);border:1px solid var(--line);border-radius:18px;padding:20px;box-shadow:0 2px 8px rgba(30,25,20,.04)}
.side button,.btn{width:100%;border:0;border-radius:12px;padding:12px 14px;margin:5px 0;font-weight:650;font-size:15px;cursor:pointer;text-align:left}
.side button{background:#f2eee7;color:#312d28}.side button.active{background:#211e1b;color:#f0b84b}.btn{width:auto;background:#1c1917;color:#fff;text-align:center}.btn.gold{background:#b77b13}.btn.secondary{background:#fff;color:#39342f;border:1px solid #d8d1c7}.btn.green{background:var(--green)}
h2{font-size:30px;margin:0 0 6px}h3{margin:0 0 8px}.muted{color:var(--muted)}.row{display:flex;gap:12px;flex-wrap:wrap}.pill{display:inline-flex;padding:6px 10px;border-radius:999px;background:#f0ece6;font-size:13px;font-weight:700}.pill.green{background:#e7f4ed;color:#256349}.pill.blue{background:#eaf2fb;color:#245e91}.pill.gold{background:#fff3d7;color:#805713}
.item{border:1px solid var(--line);border-radius:15px;padding:16px;margin:12px 0}.item strong{font-size:18px}.split{display:grid;grid-template-columns:1fr 1fr;gap:14px}
input,textarea,select{width:100%;padding:12px 13px;border:1px solid #d9d2c8;border-radius:11px;font:inherit;background:#fff;margin:5px 0 12px}.status{font-size:14px;margin-top:10px;padding:10px;border-radius:10px;background:#f4f0ea}.ok{background:#e9f6ef;color:#225f43}.bad{background:#faecec;color:#8a3030}
.metric{font-size:30px;font-weight:800}.hidden{display:none}@media(max-width:800px){.grid{grid-template-columns:1fr}.side{display:flex;overflow:auto}.side button{min-width:150px}.split{grid-template-columns:1fr}.wrap{padding:16px}h2{font-size:25px}}
</style>
</head>
<body>
<header><div class="logo">T</div><div><h1>Trade Network</h1><div class="tag">Career mobility pilot · hosted R2 preview</div></div></header>
<div class="wrap">
<div class="notice">Prototype preview with fictional demo identities. Visual perspective changes create a new authenticated demo session. Activity shown here is not proof of market success.</div>
<div class="grid">
<div class="side card">
<button onclick="loginAs('jordan')" id="nav-worker">Worker</button>
<button onclick="loginAs('owner')" id="nav-employer">Employer</button>
<button onclick="loginAs('customer')" id="nav-customer">Customer</button>
<button onclick="loginAs('admin')" id="nav-admin">Admin</button>
<div class="status" id="session">Not signed in</div>
</div>
<div>
<section id="worker" class="card hidden">
<h2>Jordan Carter</h2><p class="muted">Aspiring HVAC Technician · Oklahoma City</p>
<div class="row"><span class="pill gold">I need work this week</span><span class="pill green">45% career progress</span></div>
<h3 style="margin-top:22px">What should I do next?</h3><div id="worker-next" class="item"></div>
<h3 style="margin-top:22px">Opportunity Reality</h3><div id="opps"></div>
<h3 style="margin-top:22px">Messages & schedule</h3><div id="worker-conv" class="item muted">No accepted introduction yet.</div>
<div id="worker-meetings"></div>
<h3 style="margin-top:22px">My journey receipt</h3><div id="worker-receipt" class="item muted">Platform-recorded activity will appear here.</div>
<h3 style="margin-top:22px">Still need help? No dead end.</h3>
<p class="muted">Tell us what is blocking your next step. We record the request so it can be reviewed; submitting it does not mean a resource or provider has been found.</p>
<label>What is getting in your way?</label>
<select id="help-blocker">
<option value="TRANSPORT">Transportation</option><option value="CHILDCARE">Childcare</option>
<option value="TOOLS">Tools or equipment</option><option value="LICENSING">Licensing or certification</option>
<option value="SCHEDULE">Schedule or availability</option><option value="LOCATION">Location or distance</option>
<option value="TRAINING">Training or experience</option><option value="EMPLOYER_RESPONSE">Employer has not responded</option>
<option value="OTHER">Something else</option>
</select>
<label>Anything we should understand? (optional)</label>
<textarea id="help-details" rows="3" maxlength="1000" placeholder="Share only what is needed to explain the blocker."></textarea>
<label>How urgent is it?</label>
<select id="help-urgency"><option value="IMMEDIATELY">I need help immediately</option><option value="THIS_WEEK" selected>This week</option><option value="EXPLORING">I am exploring options</option></select>
<button class="btn gold" onclick="submitWorkerHelp()">I still need help</button>
<div id="worker-help-status" class="item muted">No help request submitted.</div>
</section>
<section id="employer" class="card hidden">
<h2>Red River Mechanical</h2><p class="muted">Employer development portal</p>
<div class="row"><span class="pill green">First Opportunity Partner</span><span class="pill blue">Will train</span></div>
<h3 style="margin-top:22px">What should I do next?</h3><div id="employer-next" class="item"></div>
<h3 style="margin-top:22px">Introduction requests</h3><div id="employer-intros"></div>
<h3 style="margin-top:22px">Conversation</h3><div id="employer-conv" class="item muted">Accept an introduction to unlock messaging.</div>
</section>
<section id="customer" class="card hidden">
<h2>I Need Help</h2><p class="muted">Submit a service request and see its truthful status.</p>
<label>Service</label><select id="service"><option>HVAC</option><option>Electrical</option><option>Plumbing</option><option>Home Repair</option></select>
<label>Describe the problem</label><textarea id="desc" rows="3" placeholder="AC is not cooling the upstairs bedrooms"></textarea>
<label>Location</label><input id="loc" value="Oklahoma City">
<button class="btn gold" onclick="submitCustomer()">Find someone to help</button>
<div id="customer-status"></div>
</section>
<section id="admin" class="card hidden">
<h2>Control Tower</h2><p class="muted">Evidence state remains UNKNOWN until evidence supports another decision.</p>
<div class="notice"><strong>Decision state: UNKNOWN</strong> · Activity is not proof of market success.</div>
<div id="metrics" class="split"></div>
<h3 style="margin-top:22px">Worker help queue</h3>
<div class="muted">Requests are platform-recorded and do not imply a resource match or completed intervention.</div>
<div id="admin-help"></div>
</section>
</div></div></div>
<script>
let token=null,role=null,user=null;
function escapeHtml(value){return String(value??"").replace(/[&<>"']/g,ch=>({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[ch]));}
async function api(path,opt={}){opt.headers={...(opt.headers||{}),"Content-Type":"application/json"};if(token)opt.headers.Authorization="Bearer "+token;const r=await fetch(path,opt);let b={};try{b=await r.json()}catch{}if(!r.ok)throw new Error(b.detail||("HTTP "+r.status));return b}
function show(id){["worker","employer","customer","admin"].forEach(x=>document.getElementById(x).classList.add("hidden"));document.getElementById(id).classList.remove("hidden");["worker","employer","customer","admin"].forEach(x=>document.getElementById("nav-"+x).classList.remove("active"));document.getElementById("nav-"+id).classList.add("active")}
async function loadWorkerReceipt(){const r=await api("/api/worker/journey-receipt");const box=document.getElementById("worker-receipt");const events=r.events||[];box.className="item";box.innerHTML='<div class="row"><span class="pill blue">'+r.evidence_scope.replaceAll("_"," ")+'</span><span class="pill">Authority '+r.authority_state+'</span></div><strong>'+events.length+' recorded milestone'+(events.length===1?'':'s')+'</strong><div class="muted" style="margin-top:8px">'+(events.length?events.map(e=>e.event_type.replaceAll("_"," ")+' · '+e.state).join("<br>"):'No journey events recorded yet.')+'</div><div class="muted" style="margin-top:10px;font-size:13px">Not a credential, license, qualifying-hours decision, or regulator acceptance.</div>'}
async function loadWorkerHelp(){const b=await api("/api/worker/help-requests");const box=document.getElementById("worker-help-status");if(!b.items.length){box.className="item muted";box.textContent="No help request submitted.";return}box.className="item";box.innerHTML=b.items.slice().reverse().map(x=>'<div><strong>'+escapeHtml(x.blocker.replaceAll("_"," "))+'</strong><div class="muted">'+escapeHtml(x.state)+' · '+escapeHtml(x.urgency.replaceAll("_"," "))+'</div><p>'+escapeHtml(x.details||"No additional details supplied.")+'</p><div class="muted" style="font-size:13px">'+escapeHtml(x.notice)+'</div>'+(x.worker_visible_update?'<div class="status">'+escapeHtml(x.worker_visible_update)+'</div>':'')+(x.worker_responses&&x.worker_responses.length?'<div class="status"><strong>Your replies</strong><br>'+x.worker_responses.map(r=>escapeHtml(r.message)).join("<br>")+'</div>':'')+(x.state==="WAITING_ON_WORKER"?'<input id="help-response-'+escapeHtml(x.id)+'" maxlength="500" placeholder="Reply to the coordinator"><button class="btn" onclick="respondWorkerHelp(\''+escapeHtml(x.id)+'\')">Send reply</button>':'')+(x.state!=="CLOSED_BY_WORKER"?'<button class="btn secondary" onclick="closeWorkerHelp(\''+escapeHtml(x.id)+'\')">Close my request</button>':'<span class="pill">Closed by you</span>')+'<span class="pill blue">'+escapeHtml(x.truth_state)+'</span></div>').join("<hr>")}
async function respondWorkerHelp(id){try{const input=document.getElementById("help-response-"+id);await api("/api/worker/help-requests/"+id+"/respond",{method:"POST",body:JSON.stringify({message:input?input.value:""})});await loadWorkerHelp();await loadNext("worker-next")}catch(e){alert(e.message)}}
async function submitWorkerHelp(){try{await api("/api/worker/help-requests",{method:"POST",body:JSON.stringify({blocker:document.getElementById("help-blocker").value,details:document.getElementById("help-details").value,urgency:document.getElementById("help-urgency").value})});document.getElementById("help-details").value="";await loadWorkerHelp()}catch(e){alert(e.message)}}
async function closeWorkerHelp(id){try{await api("/api/worker/help-requests/"+id+"/close",{method:"POST",body:"{}"});await loadWorkerHelp()}catch(e){alert(e.message)}}
async function reviewHelpRequest(id,state){try{const input=document.getElementById("help-update-"+id);await api("/api/admin/help-requests/"+id,{method:"PATCH",body:JSON.stringify({state,worker_visible_update:input?input.value:""})});await loadAdmin()}catch(e){alert(e.message)}}
async function loadNext(target){const n=await api("/api/next-action");document.getElementById(target).innerHTML='<strong>'+n.title+'</strong><div class="muted">'+n.detail+'</div><div style="margin-top:10px"><span class="pill blue">'+n.stage.replaceAll("_"," ")+'</span></div>'}
async function loginAs(name){try{const b=await api("/api/login",{method:"POST",body:JSON.stringify({identifier:name,password:"TradeDemo123!"})});token=b.session_token;role=b.roles[0];user=name;document.getElementById("session").innerHTML="<strong>"+b.name+"</strong><br>"+role;const map={WORKER:"worker",EMPLOYER:"employer",CUSTOMER:"customer",ADMIN:"admin"};show(map[role]);if(role==="WORKER")loadWorker();if(role==="EMPLOYER")loadEmployer();if(role==="ADMIN")loadAdmin()}catch(e){document.getElementById("session").textContent=e.message}}
async function loadWorker(){await loadNext("worker-next");await loadWorkerReceipt();await loadWorkerHelp();const b=await api("/api/opportunities");document.getElementById("opps").innerHTML=b.items.map(o=>'<div class="item"><div class="row"><span class="pill '+(o.will_train?'green':'blue')+'">'+o.status+'</span><span class="pill">'+o.last_confirmed+'</span></div><strong>'+o.title+'</strong><div class="muted">'+o.employer+' · '+o.location+' · '+o.pay+'</div><div style="margin-top:10px"><span class="pill gold">'+o.fit+'</span></div><button class="btn" onclick="requestIntro(\''+o.id+'\')">Request introduction</button></div>').join("");await loadWorkerConv()}
async function requestIntro(id){try{const b=await api("/api/intros",{method:"POST",body:JSON.stringify({opportunity_id:id})});alert("Introduction "+b.state);await loadNext("worker-next");await loadWorkerReceipt();await loadWorkerConv()}catch(e){alert(e.message)}}
async function loadWorkerConv(){const c=await api("/api/conversations");const box=document.getElementById("worker-conv");if(!c.items.length){box.className="item muted";box.textContent="No accepted introduction yet.";return}const conv=c.items[0];const msgs=await api("/api/conversations/"+conv.id+"/messages");box.className="item";box.innerHTML="<strong>Conversation unlocked</strong>"+msgs.items.map(m=>"<p><b>"+m.sender_name+":</b> "+m.body+"</p>").join("")+'<input id="wm" placeholder="Write a message"><button class="btn" onclick="sendMsg(\''+conv.id+'\',\'wm\')">Send</button>';const mt=await api("/api/meetings");document.getElementById("worker-meetings").innerHTML=mt.items.map(m=>'<div class="item"><strong>Interview · '+m.state+'</strong><div class="muted">'+m.start_at+'</div>'+(m.state!=="CONFIRMED"?'<button class="btn green" onclick="acceptMeeting(\''+m.id+'\')">Accept interview</button>':'')+'</div>').join("")}
async function loadEmployer(){await loadNext("employer-next");const b=await api("/api/partner/intros");document.getElementById("employer-intros").innerHTML=b.items.length?b.items.map(i=>'<div class="item"><strong>'+i.worker_name+'</strong><div class="muted">'+i.opportunity_title+' · '+i.state+'</div>'+(i.state==="PENDING"?'<button class="btn green" onclick="acceptIntro(\''+i.id+'\')">Accept introduction</button>':'')+'</div>').join(""):'<div class="item muted">No introduction requests yet. Switch to Worker and request one.</div>';const c=await api("/api/conversations");const box=document.getElementById("employer-conv");if(c.items.length){const conv=c.items[0],msgs=await api("/api/conversations/"+conv.id+"/messages");box.className="item";box.innerHTML="<strong>Conversation open</strong>"+msgs.items.map(m=>"<p><b>"+m.sender_name+":</b> "+m.body+"</p>").join("")+'<input id="em" placeholder="Message Jordan"><button class="btn" onclick="sendMsg(\''+conv.id+'\',\'em\')">Send</button><button class="btn gold" onclick="proposeMeeting(\''+conv.id+'\')">Propose interview</button>'}}
async function acceptIntro(id){await api("/api/partner/intros/"+id+"/accept",{method:"POST",body:"{}"});await loadEmployer()}
async function sendMsg(conv,input){const el=document.getElementById(input);if(!el.value)return;await api("/api/conversations/"+conv+"/messages",{method:"POST",body:JSON.stringify({body:el.value})});if(role==="WORKER"){await loadNext("worker-next");await loadWorkerReceipt();loadWorkerConv()}else{await loadNext("employer-next");loadEmployer()}}
async function proposeMeeting(conv){await api("/api/meetings",{method:"POST",body:JSON.stringify({conversation_id:conv,start_at:"Tomorrow 10:00 AM",end_at:"Tomorrow 10:30 AM"})});await loadNext("employer-next");alert("Interview proposed")}
async function acceptMeeting(id){await api("/api/meetings/"+id+"/accept",{method:"POST",body:"{}"});await loadNext("worker-next");await loadWorkerConv()}
async function submitCustomer(){const b=await api("/api/customer/requests",{method:"POST",body:JSON.stringify({service_category:document.getElementById("service").value,description:document.getElementById("desc").value,location_text:document.getElementById("loc").value})});document.getElementById("customer-status").innerHTML='<div class="item"><strong>'+b.state+'</strong><div class="muted">Matched business: '+b.matched_business+'</div><span class="pill blue">'+b.truth_state+'</span></div>'}
async function loadAdmin(){const b=await api("/api/admin/control-tower");document.getElementById("metrics").innerHTML=Object.entries(b.counts).map(([k,v])=>'<div class="item"><div class="metric">'+v+'</div><div class="muted">'+k.replaceAll("_"," ")+'</div></div>').join("");const q=await api("/api/admin/help-requests");document.getElementById("admin-help").innerHTML=q.items.length?q.items.map(x=>'<div class="item"><strong>'+escapeHtml(x.worker_name)+'</strong><div class="muted">'+escapeHtml(x.blocker.replaceAll("_"," "))+' · '+escapeHtml(x.urgency.replaceAll("_"," "))+' · '+escapeHtml(x.state)+'</div><p>'+escapeHtml(x.details||"No additional details.")+'</p>'+(x.worker_visible_update?'<div class="status">'+escapeHtml(x.worker_visible_update)+'</div>':'')+(x.worker_responses&&x.worker_responses.length?'<div class="status"><strong>Worker replies</strong><br>'+x.worker_responses.map(r=>escapeHtml(r.message)).join("<br>")+'</div>':'')+(x.state!=="CLOSED_BY_WORKER"?'<input id="help-update-'+escapeHtml(x.id)+'" placeholder="Optional worker-visible update" maxlength="500"><button class="btn secondary" onclick="reviewHelpRequest(\''+escapeHtml(x.id)+'\',\'IN_REVIEW\')">Mark in review</button><button class="btn gold" onclick="reviewHelpRequest(\''+escapeHtml(x.id)+'\',\'WAITING_ON_WORKER\')">Ask worker for info</button>':'<span class="pill">Closed by worker</span>')+'<span class="pill blue">'+escapeHtml(x.truth_state)+'</span></div>').join(""):'<div class="item muted">No worker help requests recorded.</div>'}
loginAs("jordan");
</script></body></html>"""

@app.get("/", response_class=HTMLResponse)
def root():
    return HTML

@app.get("/app", response_class=HTMLResponse)
def app_page():
    return HTML
