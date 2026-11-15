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
