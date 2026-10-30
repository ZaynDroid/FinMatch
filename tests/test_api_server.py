"""
Tests for REST API endpoints without requiring httpx.
Tests ASGI endpoints directly using Starlette Request objects and asyncio.
"""

import json
import asyncio
import pytest
from starlette.requests import Request
from server import api_health, api_login, api_register, api_get_businesses


def build_request(method: str = "GET", data: dict = None) -> Request:
    """Construct an ASGI Request object directly for unit testing."""
    payload_bytes = json.dumps(data or {}).encode("utf-8")
    sent = False

    async def receive():
        nonlocal sent
        if not sent:
            sent = True
            return {"type": "http.request", "body": payload_bytes, "more_body": False}
        return {"type": "http.request", "body": b"", "more_body": False}

    scope = {
        "type": "http",
        "method": method,
        "path": "/",
        "headers": [(b"content-type", b"application/json")],
    }
    return Request(scope, receive)


def test_api_health():
    req = build_request("GET")
    resp = asyncio.run(api_health(req))
    assert resp.status_code == 200
    body = json.loads(resp.body.decode())
    assert body["status"] == "ok"


def test_api_login_success():
    # Login with email
    req1 = build_request("POST", {"id": "user@finmatch.demo", "pw": "demo123", "role": "user"})
    resp1 = asyncio.run(api_login(req1))
    assert resp1.status_code == 200
    b1 = json.loads(resp1.body.decode())
    assert b1["ok"] is True
    assert b1["user"]["email"] == "user@finmatch.demo"
    assert b1["user"]["business_name"] == "Sharma Traders"

    # Login with 10-digit mobile number
    req2 = build_request("POST", {"id": "9876543210", "pw": "demo123", "role": "user"})
    resp2 = asyncio.run(api_login(req2))
    assert resp2.status_code == 200
    b2 = json.loads(resp2.body.decode())
    assert b2["ok"] is True
    assert b2["user"]["mobile"] == "9876543210"

    # Login as Admin
    req3 = build_request("POST", {"id": "admin@finmatch.demo", "pw": "admin123", "role": "admin"})
    resp3 = asyncio.run(api_login(req3))
    assert resp3.status_code == 200
    b3 = json.loads(resp3.body.decode())
    assert b3["ok"] is True
    assert b3["user"]["role"] == "admin"


def test_api_login_failure():
    req = build_request("POST", {"id": "user@finmatch.demo", "pw": "wrong_password"})
    resp = asyncio.run(api_login(req))
    assert resp.status_code == 401
    b = json.loads(resp.body.decode())
    assert b["ok"] is False
    assert "Incorrect password" in b["error"]


def test_api_register_new_business():
    import uuid
    uid_suffix = uuid.uuid4().hex[:6]
    mob_suffix = f"{uuid.uuid4().int % 100000000:08d}"
    clean_mob = f"98{mob_suffix}"
    
    payload = {
        "business_name": f"API Traders {uid_suffix}",
        "owner_name": "Rohan Verma",
        "email": f"rohan_{uid_suffix}@apibiz.demo",
        "mobile": clean_mob,
        "password": "mypassword123",
        "role": "user",
    }
    req = build_request("POST", payload)
    resp = asyncio.run(api_register(req))
    assert resp.status_code == 200
    b = json.loads(resp.body.decode())
    assert b["ok"] is True
    assert b["user"]["business_name"] == f"API Traders {uid_suffix}"

    # Now verify login works with the new account
    login_req = build_request("POST", {"id": clean_mob, "pw": "mypassword123"})
    login_resp = asyncio.run(api_login(login_req))
    assert login_resp.status_code == 200
    assert json.loads(login_resp.body.decode())["ok"] is True


def test_api_get_businesses():
    req = build_request("GET")
    resp = asyncio.run(api_get_businesses(req))
    assert resp.status_code == 200
    b = json.loads(resp.body.decode())
    assert b["ok"] is True
    assert len(b["businesses"]) >= 1
