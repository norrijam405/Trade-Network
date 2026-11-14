from fastapi import FastAPI, HTTPException, Header
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Optional
import secrets
from datetime import datetime, timezone

app = FastAPI(title="Trade Network Hosted Preview R2")

USERS = {
    "jordan": {"password": "TradeDemo123!", "role": "WORKER", "name": "Jordan Carter"},
    "owner": {"password": "TradeDemo123!", "role": "EMPLOYER", "name": "Red River Mechanical"},
    "customer": {"password": "TradeDemo123!", "role": "CUSTOMER", "name": "Demo Customer"},
    "admin": {"password": "TradeDemo123!", "role": "ADMIN", "name": "Demo Administrator"},
}
TOKENS = {}
OPPORTUNITIES = [
    {"id":"n2","title":"HVAC Trainee","employer":"Red River Mechanical","pay":"Training wage","status":"OPEN NOW","will_train":True,"last_confirmed":"Today","fit":"Best Career Move","location":"Oklahoma City"},
    {"id":"n1","title":"Warehouse Helper","employer":"Red River Mechanical","pay":"$18/hr reported","status":"OPEN NOW","will_train":False,"last_confirmed":"Today","fit":"Fastest Money Move","location":"Oklahoma City"},
]
INTROS = []
CONVERSATIONS = []
MESSAGES = []
MEETINGS = []
CUSTOMER_REQUESTS = []

def now():
    return datetime.now(timezone.utc).isoformat()

def auth_header(authorization: Optional[str]):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "authentication required")
    token = authorization.split(" ", 1)[1]
    user = TOKENS.get(token)
    if not user:
        raise HTTPException(401, "invalid session")
    return user

def require_role(user, role):
    if user["role"] != role:
        raise HTTPException(403, f"role denied: {role}")

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
    TOKENS[token] = {"username":key, **u}
    return {"session_token":token,"user_id":key,"roles":[u["role"]],"name":u["name"]}

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
    c = next((x for x in CONVERSATIONS if x["id"]==conversation_id), None)
    if not c or u["username"] not in (c["worker"],c["employer"]):
        raise HTTPException(403, "conversation access denied")
    m = {"id":f"msg-{len(MESSAGES)+1}","conversation_id":conversation_id,"sender":u["username"],"sender_name":u["name"],"body":body.body,"created_at":now()}
    MESSAGES.append(m)
    return m

@app.post("/api/meetings")
def create_meeting(body: MeetingBody, authorization: Optional[str] = Header(None)):
    u = auth_header(authorization)
    c = next((x for x in CONVERSATIONS if x["id"]==body.conversation_id), None)
    if not c or u["username"] not in (c["worker"],c["employer"]):
        raise HTTPException(403, "conversation access denied")
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
    item = {"id":f"req-{len(CUSTOMER_REQUESTS)+1}","customer":u["username"],**body.model_dump(),"state":"MATCHED","matched_business":"Red River Mechanical","truth_state":"DEMO","created_at":now()}
    CUSTOMER_REQUESTS.append(item)
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
<h3 style="margin-top:22px">Opportunity Reality</h3><div id="opps"></div>
<h3 style="margin-top:22px">Messages & schedule</h3><div id="worker-conv" class="item muted">No accepted introduction yet.</div>
<div id="worker-meetings"></div>
</section>
<section id="employer" class="card hidden">
<h2>Red River Mechanical</h2><p class="muted">Employer development portal</p>
<div class="row"><span class="pill green">First Opportunity Partner</span><span class="pill blue">Will train</span></div>
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
</section>
</div></div></div>
<script>
let token=null,role=null,user=null;
async function api(path,opt={}){opt.headers={...(opt.headers||{}),"Content-Type":"application/json"};if(token)opt.headers.Authorization="Bearer "+token;const r=await fetch(path,opt);let b={};try{b=await r.json()}catch{}if(!r.ok)throw new Error(b.detail||("HTTP "+r.status));return b}
function show(id){["worker","employer","customer","admin"].forEach(x=>document.getElementById(x).classList.add("hidden"));document.getElementById(id).classList.remove("hidden");["worker","employer","customer","admin"].forEach(x=>document.getElementById("nav-"+x).classList.remove("active"));document.getElementById("nav-"+id).classList.add("active")}
async function loginAs(name){try{const b=await api("/api/login",{method:"POST",body:JSON.stringify({identifier:name,password:"TradeDemo123!"})});token=b.session_token;role=b.roles[0];user=name;document.getElementById("session").innerHTML="<strong>"+b.name+"</strong><br>"+role;const map={WORKER:"worker",EMPLOYER:"employer",CUSTOMER:"customer",ADMIN:"admin"};show(map[role]);if(role==="WORKER")loadWorker();if(role==="EMPLOYER")loadEmployer();if(role==="ADMIN")loadAdmin()}catch(e){document.getElementById("session").textContent=e.message}}
async function loadWorker(){const b=await api("/api/opportunities");document.getElementById("opps").innerHTML=b.items.map(o=>'<div class="item"><div class="row"><span class="pill '+(o.will_train?'green':'blue')+'">'+o.status+'</span><span class="pill">'+o.last_confirmed+'</span></div><strong>'+o.title+'</strong><div class="muted">'+o.employer+' · '+o.location+' · '+o.pay+'</div><div style="margin-top:10px"><span class="pill gold">'+o.fit+'</span></div><button class="btn" onclick="requestIntro(\''+o.id+'\')">Request introduction</button></div>').join("");await loadWorkerConv()}
async function requestIntro(id){try{const b=await api("/api/intros",{method:"POST",body:JSON.stringify({opportunity_id:id})});alert("Introduction "+b.state);await loadWorkerConv()}catch(e){alert(e.message)}}
async function loadWorkerConv(){const c=await api("/api/conversations");const box=document.getElementById("worker-conv");if(!c.items.length){box.className="item muted";box.textContent="No accepted introduction yet.";return}const conv=c.items[0];const msgs=await api("/api/conversations/"+conv.id+"/messages");box.className="item";box.innerHTML="<strong>Conversation unlocked</strong>"+msgs.items.map(m=>"<p><b>"+m.sender_name+":</b> "+m.body+"</p>").join("")+'<input id="wm" placeholder="Write a message"><button class="btn" onclick="sendMsg(\''+conv.id+'\',\'wm\')">Send</button>';const mt=await api("/api/meetings");document.getElementById("worker-meetings").innerHTML=mt.items.map(m=>'<div class="item"><strong>Interview · '+m.state+'</strong><div class="muted">'+m.start_at+'</div>'+(m.state!=="CONFIRMED"?'<button class="btn green" onclick="acceptMeeting(\''+m.id+'\')">Accept interview</button>':'')+'</div>').join("")}
async function loadEmployer(){const b=await api("/api/partner/intros");document.getElementById("employer-intros").innerHTML=b.items.length?b.items.map(i=>'<div class="item"><strong>'+i.worker_name+'</strong><div class="muted">'+i.opportunity_title+' · '+i.state+'</div>'+(i.state==="PENDING"?'<button class="btn green" onclick="acceptIntro(\''+i.id+'\')">Accept introduction</button>':'')+'</div>').join(""):'<div class="item muted">No introduction requests yet. Switch to Worker and request one.</div>';const c=await api("/api/conversations");const box=document.getElementById("employer-conv");if(c.items.length){const conv=c.items[0],msgs=await api("/api/conversations/"+conv.id+"/messages");box.className="item";box.innerHTML="<strong>Conversation open</strong>"+msgs.items.map(m=>"<p><b>"+m.sender_name+":</b> "+m.body+"</p>").join("")+'<input id="em" placeholder="Message Jordan"><button class="btn" onclick="sendMsg(\''+conv.id+'\',\'em\')">Send</button><button class="btn gold" onclick="proposeMeeting(\''+conv.id+'\')">Propose interview</button>'}}
async function acceptIntro(id){await api("/api/partner/intros/"+id+"/accept",{method:"POST",body:"{}"});await loadEmployer()}
async function sendMsg(conv,input){const el=document.getElementById(input);if(!el.value)return;await api("/api/conversations/"+conv+"/messages",{method:"POST",body:JSON.stringify({body:el.value})});if(role==="WORKER")loadWorkerConv();else loadEmployer()}
async function proposeMeeting(conv){await api("/api/meetings",{method:"POST",body:JSON.stringify({conversation_id:conv,start_at:"Tomorrow 10:00 AM",end_at:"Tomorrow 10:30 AM"})});alert("Interview proposed")}
async function acceptMeeting(id){await api("/api/meetings/"+id+"/accept",{method:"POST",body:"{}"});await loadWorkerConv()}
async function submitCustomer(){const b=await api("/api/customer/requests",{method:"POST",body:JSON.stringify({service_category:document.getElementById("service").value,description:document.getElementById("desc").value,location_text:document.getElementById("loc").value})});document.getElementById("customer-status").innerHTML='<div class="item"><strong>'+b.state+'</strong><div class="muted">Matched business: '+b.matched_business+'</div><span class="pill blue">'+b.truth_state+'</span></div>'}
async function loadAdmin(){const b=await api("/api/admin/control-tower");document.getElementById("metrics").innerHTML=Object.entries(b.counts).map(([k,v])=>'<div class="item"><div class="metric">'+v+'</div><div class="muted">'+k.replaceAll("_"," ")+'</div></div>').join("")}
loginAs("jordan");
</script></body></html>"""

@app.get("/", response_class=HTMLResponse)
def root():
    return HTML

@app.get("/app", response_class=HTMLResponse)
def app_page():
    return HTML
"""
