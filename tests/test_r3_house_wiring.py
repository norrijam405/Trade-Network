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
    ns["HELP_REQUESTS"].clear()
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


def test_public_persistence_status_is_minimized():
    r = client.get("/api/persistence")
    assert r.status_code == 200
    body = r.json()
    assert "event_count" not in body
    assert "restart_count" not in body
    assert "first_seen_at" not in body
    assert "last_seen_at" not in body
    assert set(body).issuperset({"enabled", "ready", "mode", "house_selftest_ready", "status"})

def test_non_admin_cannot_read_detailed_persistence_status():
    customer = login("customer")
    r = client.get("/api/admin/persistence", headers=auth(customer))
    assert r.status_code == 403

def test_admin_can_read_detailed_persistence_status():
    admin = login("admin")
    r = client.get("/api/admin/persistence", headers=auth(admin))
    assert r.status_code == 200
    body = r.json()
    assert "event_count" in body
    assert "restart_count" in body


def test_non_admin_cannot_read_standby_status():
    customer = login("customer")
    r = client.get("/api/admin/standby", headers=auth(customer))
    assert r.status_code == 403

def test_admin_can_read_standby_status_without_secret_in_ci():
    admin = login("admin")
    r = client.get("/api/admin/standby", headers=auth(admin))
    assert r.status_code == 200
    body = r.json()
    assert body["provider"] == "neon"
    assert "url" not in body
    assert "password" not in body


def test_worker_next_action_progresses_through_real_journey():
    worker = login("jordan")
    owner = login("owner")

    r = client.get("/api/next-action", headers=auth(worker))
    assert r.status_code == 200
    assert r.json()["code"] == "REQUEST_INTRO"

    intro = client.post("/api/intros", headers=auth(worker), json={"opportunity_id": "n2"}).json()
    r = client.get("/api/next-action", headers=auth(worker))
    assert r.json()["code"] == "WAIT_FOR_EMPLOYER"

    accepted = client.post(f"/api/partner/intros/{intro['id']}/accept", headers=auth(owner), json={})
    assert accepted.status_code == 200
    conv = accepted.json()["conversation"]

    r = client.get("/api/next-action", headers=auth(worker))
    assert r.json()["code"] == "SEND_FIRST_MESSAGE"

    msg = client.post(
        f"/api/conversations/{conv['id']}/messages",
        headers=auth(worker),
        json={"body": "Fictional hello"},
    )
    assert msg.status_code == 200
    r = client.get("/api/next-action", headers=auth(worker))
    assert r.json()["code"] == "WAIT_FOR_INTERVIEW"

    proposed = client.post(
        "/api/meetings",
        headers=auth(owner),
        json={
            "conversation_id": conv["id"],
            "start_at": "Tomorrow 10:00 AM",
            "end_at": "Tomorrow 10:30 AM",
        },
    )
    assert proposed.status_code == 200
    r = client.get("/api/next-action", headers=auth(worker))
    assert r.json()["code"] == "ACCEPT_INTERVIEW"

    accepted_meeting = client.post(
        f"/api/meetings/{proposed.json()['id']}/accept",
        headers=auth(worker),
        json={},
    )
    assert accepted_meeting.status_code == 200
    assert accepted_meeting.json()["state"] == "CONFIRMED"

    r = client.get("/api/next-action", headers=auth(worker))
    assert r.json()["code"] == "PREPARE_INTERVIEW"


def test_employer_next_action_progresses_through_real_journey():
    worker = login("jordan")
    owner = login("owner")

    r = client.get("/api/next-action", headers=auth(owner))
    assert r.status_code == 200
    assert r.json()["code"] == "WAIT_FOR_INTRO"

    intro = client.post("/api/intros", headers=auth(worker), json={"opportunity_id": "n2"}).json()
    r = client.get("/api/next-action", headers=auth(owner))
    assert r.json()["code"] == "REVIEW_INTRO"

    accepted = client.post(f"/api/partner/intros/{intro['id']}/accept", headers=auth(owner), json={}).json()
    conv = accepted["conversation"]

    r = client.get("/api/next-action", headers=auth(owner))
    assert r.json()["code"] == "SEND_FIRST_MESSAGE"

    client.post(
        f"/api/conversations/{conv['id']}/messages",
        headers=auth(owner),
        json={"body": "Fictional employer message"},
    )
    r = client.get("/api/next-action", headers=auth(owner))
    assert r.json()["code"] == "PROPOSE_INTERVIEW"

    proposed = client.post(
        "/api/meetings",
        headers=auth(owner),
        json={
            "conversation_id": conv["id"],
            "start_at": "Tomorrow 10:00 AM",
            "end_at": "Tomorrow 10:30 AM",
        },
    )
    assert proposed.status_code == 200
    r = client.get("/api/next-action", headers=auth(owner))
    assert r.json()["code"] == "WAIT_FOR_WORKER_CONFIRMATION"

    client.post(
        f"/api/meetings/{proposed.json()['id']}/accept",
        headers=auth(worker),
        json={},
    )
    r = client.get("/api/next-action", headers=auth(owner))
    assert r.json()["code"] == "PREPARE_INTERVIEW"


def test_customer_and_admin_cannot_use_worker_employer_next_action():
    customer = login("customer")
    admin = login("admin")
    assert client.get("/api/next-action", headers=auth(customer)).status_code == 403
    assert client.get("/api/next-action", headers=auth(admin)).status_code == 403


def test_worker_journey_receipt_is_role_scoped_and_authority_bounded():
    worker = login("jordan")
    owner = login("owner")

    denied = client.get("/api/worker/journey-receipt", headers=auth(owner))
    assert denied.status_code == 403

    empty = client.get("/api/worker/journey-receipt", headers=auth(worker))
    assert empty.status_code == 200
    body = empty.json()
    assert body["receipt_type"] == "CAREER_JOURNEY_ACTIVITY"
    assert body["evidence_scope"] == "PLATFORM_RECORDED_ACTIVITY_ONLY"
    assert body["authority_state"] == "UNKNOWN"
    assert body["qualifying_hours_authority"] == "NONE"
    assert body["credential_acceptance_authority"] == "NONE"
    assert body["events"] == []
    text = str(body).lower()
    assert "credential" in text
    assert "regulator acceptance" in text

def test_worker_journey_receipt_records_platform_activity_without_overclaiming():
    worker = login("jordan")
    owner = login("owner")

    intro = client.post("/api/intros", headers=auth(worker), json={"opportunity_id": "n2"}).json()
    accepted = client.post(f"/api/partner/intros/{intro['id']}/accept", headers=auth(owner), json={}).json()
    conv = accepted["conversation"]

    client.post(
        f"/api/conversations/{conv['id']}/messages",
        headers=auth(worker),
        json={"body": "Fictional worker message"},
    )

    meeting = client.post(
        "/api/meetings",
        headers=auth(owner),
        json={
            "conversation_id": conv["id"],
            "start_at": "Tomorrow 10:00 AM",
            "end_at": "Tomorrow 10:30 AM",
        },
    ).json()

    client.post(f"/api/meetings/{meeting['id']}/accept", headers=auth(worker), json={})

    receipt = client.get("/api/worker/journey-receipt", headers=auth(worker))
    assert receipt.status_code == 200
    body = receipt.json()
    event_types = {e["event_type"] for e in body["events"]}
    assert "INTRO_REQUESTED" in event_types
    assert "INTRO_ACCEPTED" in event_types
    assert "WORKER_MESSAGE_SENT" in event_types
    assert "INTERVIEW_CONFIRMED" in event_types
    assert all(e["truth_state"] == "SUPPORTED" for e in body["events"])
    assert body["current_stage"] == "MEETING_CONFIRMED"
    assert body["authority_state"] == "UNKNOWN"


def test_worker_no_dead_end_help_request_is_scoped_deduplicated_and_truth_bounded():
    worker = login("jordan")
    owner = login("owner")
    customer = login("customer")
    admin = login("admin")
    payload = {
        "blocker": "TRANSPORT",
        "details": "Fictional bus route ends before shift start.",
        "urgency": "THIS_WEEK",
    }

    first = client.post("/api/worker/help-requests", headers=auth(worker), json=payload)
    second = client.post("/api/worker/help-requests", headers=auth(worker), json=payload)
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    assert first.json()["state"] == "OPEN"
    assert first.json()["truth_state"] == "SUPPORTED"
    assert first.json()["evidence_scope"] == "PLATFORM_RECORDED_REQUEST_ONLY"
    assert first.json()["resolution_authority"] == "NONE"
    assert "has been confirmed or contacted" in first.json()["notice"]

    own = client.get("/api/worker/help-requests", headers=auth(worker))
    assert own.status_code == 200
    assert len(own.json()["items"]) == 1

    assert client.get("/api/worker/help-requests", headers=auth(owner)).status_code == 403
    assert client.post("/api/worker/help-requests", headers=auth(customer), json=payload).status_code == 403
    assert client.get("/api/admin/help-requests", headers=auth(worker)).status_code == 403

    queue = client.get("/api/admin/help-requests", headers=auth(admin))
    assert queue.status_code == 200
    assert len(queue.json()["items"]) == 1
    tower = client.get("/api/admin/control-tower", headers=auth(admin)).json()
    assert tower["counts"]["worker_help_requests"] == 1
    assert tower["counts"]["open_worker_help_requests"] == 1
    assert "help_requests" in runtime.PERSISTED
    assert runtime.PERSISTED["help_requests"] is runtime.namespace["HELP_REQUESTS"]


def test_worker_help_request_rejects_unknown_blockers_and_oversized_details():
    worker = login("jordan")
    bad_blocker = client.post(
        "/api/worker/help-requests",
        headers=auth(worker),
        json={"blocker": "MONEY", "details": "fictional"},
    )
    assert bad_blocker.status_code == 422

    too_long = client.post(
        "/api/worker/help-requests",
        headers=auth(worker),
        json={"blocker": "OTHER", "details": "x" * 1001},
    )
    assert too_long.status_code == 422


def test_admin_help_triage_is_bounded_and_worker_visible():
    worker = login("jordan")
    admin = login("admin")
    request = client.post(
        "/api/worker/help-requests",
        headers=auth(worker),
        json={"blocker": "CHILDCARE", "details": "Fictional shift begins before childcare opens."},
    ).json()

    in_review = client.patch(
        f"/api/admin/help-requests/{request['id']}",
        headers=auth(admin),
        json={"state": "IN_REVIEW", "worker_visible_update": "A coordinator is reviewing the request."},
    )
    assert in_review.status_code == 200
    assert in_review.json()["state"] == "IN_REVIEW"
    assert in_review.json()["resolution_authority"] == "NONE"

    waiting = client.patch(
        f"/api/admin/help-requests/{request['id']}",
        headers=auth(admin),
        json={"state": "WAITING_ON_WORKER", "worker_visible_update": "Please confirm the days and hours you need."},
    )
    assert waiting.status_code == 200
    own = client.get("/api/worker/help-requests", headers=auth(worker)).json()["items"][0]
    assert own["state"] == "WAITING_ON_WORKER"
    assert own["worker_visible_update"] == "Please confirm the days and hours you need."

    false_resolution = client.patch(
        f"/api/admin/help-requests/{request['id']}",
        headers=auth(admin),
        json={"state": "RESOLVED", "worker_visible_update": "Resolved."},
    )
    assert false_resolution.status_code == 422


def test_worker_can_close_only_their_own_help_request():
    worker = login("jordan")
    owner = login("owner")
    request = client.post(
        "/api/worker/help-requests",
        headers=auth(worker),
        json={"blocker": "TOOLS", "details": "Fictional starter tool gap."},
    ).json()

    denied = client.post(f"/api/worker/help-requests/{request['id']}/close", headers=auth(owner), json={})
    assert denied.status_code == 403

    closed = client.post(f"/api/worker/help-requests/{request['id']}/close", headers=auth(worker), json={})
    assert closed.status_code == 200
    assert closed.json()["state"] == "CLOSED_BY_WORKER"
    assert closed.json()["resolution_authority"] == "NONE"

def test_worker_can_reply_to_admin_follow_up_and_return_request_to_review_queue():
    worker = login("jordan")
    admin = login("admin")
    employer = login("owner")
    request = client.post(
        "/api/worker/help-requests",
        headers=auth(worker),
        json={"blocker": "TRANSPORT", "details": "Fictional schedule and transport conflict."},
    ).json()

    waiting = client.patch(
        f"/api/admin/help-requests/{request['id']}",
        headers=auth(admin),
        json={"state": "WAITING_ON_WORKER", "worker_visible_update": "Please confirm which shifts you can reach."},
    )
    assert waiting.status_code == 200
    next_action = client.get("/api/next-action", headers=auth(worker))
    assert next_action.status_code == 200
    assert next_action.json()["code"] == "RESPOND_TO_HELP_REQUEST"

    denied = client.post(
        f"/api/worker/help-requests/{request['id']}/respond",
        headers=auth(employer),
        json={"message": "Fictional response."},
    )
    assert denied.status_code == 403

    blank = client.post(
        f"/api/worker/help-requests/{request['id']}/respond",
        headers=auth(worker),
        json={"message": "   "},
    )
    assert blank.status_code == 422

    reply = client.post(
        f"/api/worker/help-requests/{request['id']}/respond",
        headers=auth(worker),
        json={"message": "I can reach the Tuesday and Thursday shifts."},
    )
    assert reply.status_code == 200
    assert reply.json()["state"] == "OPEN"
    assert reply.json()["resolution_authority"] == "NONE"
    assert reply.json()["worker_responses"][-1]["truth_state"] == "SUPPORTED"
    assert reply.json()["worker_responses"][-1]["message"] == "I can reach the Tuesday and Thursday shifts."

    duplicate = client.post(
        f"/api/worker/help-requests/{request['id']}/respond",
        headers=auth(worker),
        json={"message": "I can reach the Tuesday and Thursday shifts."},
    )
    assert duplicate.status_code == 409

    admin_queue = client.get("/api/admin/help-requests", headers=auth(admin))
    assert admin_queue.status_code == 200
    assert admin_queue.json()["items"][0]["worker_responses"][-1]["message"] == "I can reach the Tuesday and Thursday shifts."
    assert client.get("/api/next-action", headers=auth(worker)).json()["code"] != "RESPOND_TO_HELP_REQUEST"

