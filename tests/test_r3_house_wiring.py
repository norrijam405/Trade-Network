import os
os.environ.pop("DATABASE_URL", None)

import pytest
from fastapi.testclient import TestClient
import preview_runner as runtime

client = TestClient(runtime.app)

@pytest.fixture(autouse=True)
def reset_demo_state():
    ns = runtime.namespace
    ns["TOKENS"].clear()
    ns["INTROS"].clear()
    ns["CONVERSATIONS"].clear()
    ns["MESSAGES"].clear()
    ns["MEETINGS"].clear()
    ns["CUSTOMER_REQUESTS"].clear()
    yield

def login(identifier):
    r = client.post("/api/login", json={"identifier": identifier, "password": "TradeDemo123!"})
    assert r.status_code == 200
    return r.json()["session_token"]

def auth(token):
    return {"Authorization": f"Bearer {token}"}

def test_invalid_session_fails_closed():
    r = client.get("/api/opportunities", headers=auth("fictional-invalid-token"))
    assert r.status_code == 401

def test_wrong_role_cannot_read_worker_opportunities():
    owner = login("owner")
    r = client.get("/api/opportunities", headers=auth(owner))
    assert r.status_code == 403

def test_duplicate_intro_is_suppressed():
    worker = login("jordan")
    a = client.post("/api/intros", headers=auth(worker), json={"opportunity_id": "n2"})
    b = client.post("/api/intros", headers=auth(worker), json={"opportunity_id": "n2"})
    assert a.status_code == 200
    assert b.status_code == 200
    assert a.json()["id"] == b.json()["id"]
    assert len(runtime.namespace["INTROS"]) == 1

def test_employer_accept_unlocks_one_conversation():
    worker = login("jordan")
    owner = login("owner")
    intro = client.post("/api/intros", headers=auth(worker), json={"opportunity_id": "n2"}).json()
    accepted = client.post(f"/api/partner/intros/{intro['id']}/accept", headers=auth(owner), json={})
    assert accepted.status_code == 200
    assert accepted.json()["intro"]["state"] == "ACCEPTED"
    assert len(runtime.namespace["CONVERSATIONS"]) == 1

def test_customer_cannot_access_admin_control_tower():
    customer = login("customer")
    r = client.get("/api/admin/control-tower", headers=auth(customer))
    assert r.status_code == 403

def test_admin_decision_state_defaults_unknown():
    admin = login("admin")
    r = client.get("/api/admin/control-tower", headers=auth(admin))
    assert r.status_code == 200
    assert r.json()["decision_state"] == "UNKNOWN"


def test_second_employer_cannot_see_or_accept_first_employer_intro():
    worker = login("jordan")
    owner2 = login("owner2")
    intro = client.post("/api/intros", headers=auth(worker), json={"opportunity_id": "n2"}).json()
    listed = client.get("/api/partner/intros", headers=auth(owner2))
    assert listed.status_code == 200
    assert listed.json()["items"] == []
    accepted = client.post(f"/api/partner/intros/{intro['id']}/accept", headers=auth(owner2), json={})
    assert accepted.status_code == 404

def test_duplicate_meeting_proposal_is_suppressed():
    worker = login("jordan")
    owner = login("owner")
    intro = client.post("/api/intros", headers=auth(worker), json={"opportunity_id": "n2"}).json()
    conv = client.post(f"/api/partner/intros/{intro['id']}/accept", headers=auth(owner), json={}).json()["conversation"]
    payload = {"conversation_id": conv["id"], "start_at": "Tomorrow 10:00 AM", "end_at": "Tomorrow 10:30 AM"}
    a = client.post("/api/meetings", headers=auth(owner), json=payload)
    b = client.post("/api/meetings", headers=auth(owner), json=payload)
    assert a.status_code == 200
    assert b.status_code == 200
    assert a.json()["id"] == b.json()["id"]
    assert len(runtime.namespace["MEETINGS"]) == 1

def test_duplicate_customer_request_is_suppressed():
    customer = login("customer")
    payload = {
        "service_category": "HVAC",
        "description": "Fictional AC not cooling",
        "location_text": "Oklahoma City",
        "urgency": "THIS_WEEK",
        "learner_preference": "NO_PREFERENCE",
    }
    a = client.post("/api/customer/requests", headers=auth(customer), json=payload)
    b = client.post("/api/customer/requests", headers=auth(customer), json=payload)
    assert a.status_code == 200
    assert b.status_code == 200
    assert a.json()["id"] == b.json()["id"]
    assert len(runtime.namespace["CUSTOMER_REQUESTS"]) == 1

def test_blank_message_is_rejected():
    worker = login("jordan")
    owner = login("owner")
    intro = client.post("/api/intros", headers=auth(worker), json={"opportunity_id": "n2"}).json()
    conv = client.post(f"/api/partner/intros/{intro['id']}/accept", headers=auth(owner), json={}).json()["conversation"]
    r = client.post(f"/api/conversations/{conv['id']}/messages", headers=auth(worker), json={"body": "   "})
    assert r.status_code == 422
    assert len(runtime.namespace["MESSAGES"]) == 0


def test_expired_session_is_rejected_and_removed():
    worker = login("jordan")
    runtime.namespace["TOKENS"][worker]["expires_at"] = 0
    r = client.get("/api/opportunities", headers=auth(worker))
    assert r.status_code == 401
    assert worker not in runtime.namespace["TOKENS"]

def test_logout_revokes_session():
    worker = login("jordan")
    out = client.post("/api/logout", headers=auth(worker), json={})
    assert out.status_code == 200
    assert out.json()["ok"] is True
    r = client.get("/api/opportunities", headers=auth(worker))
    assert r.status_code == 401
