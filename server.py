"""
REST API and Web Server for FinMatch.
Provides authentication, registration, businesses management, and static frontend serving.
Powered by Starlette and Uvicorn.
"""

from __future__ import annotations
import json
import os
import sys
from pathlib import Path

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

from backend.service import ReconciliationService

service = ReconciliationService(db_path="finmatch.db")


async def api_health(request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok", "app": "FinMatch Unified Server", "version": "1.0.0"})


async def api_login(request: Request) -> JSONResponse:
    try:
        data = await request.json()
    except Exception:
        return JSONResponse({"ok": False, "error": "Invalid JSON payload."}, status_code=400)

    # Support multiple key styles: (id, pw) or (login_id, password) or (email/mobile)
    login_id = data.get("id") or data.get("login_id") or data.get("email") or data.get("mobile")
    password = data.get("pw") or data.get("password")
    role = data.get("role")  # optional

    if not login_id or not password:
        return JSONResponse(
            {"ok": False, "error": "Mobile/email and password are required."},
            status_code=400,
        )

    try:
        user = service.login(login_id=str(login_id).strip(), password=str(password), role=role)
        return JSONResponse({"ok": True, "user": user.to_dict()})
    except ValueError as ve:
        return JSONResponse({"ok": False, "error": str(ve)}, status_code=401)
    except Exception as exc:
        return JSONResponse({"ok": False, "error": f"Internal error: {str(exc)}"}, status_code=500)


async def api_register(request: Request) -> JSONResponse:
    try:
        data = await request.json()
    except Exception:
        return JSONResponse({"ok": False, "error": "Invalid JSON payload."}, status_code=400)

    bname = data.get("business_name") or data.get("name")
    oname = data.get("owner_name") or data.get("owner")
    email = data.get("email")
    mobile = data.get("mobile") or data.get("phone")
    password = data.get("password") or data.get("pw")
    role = data.get("role") or "user"

    # If email wasn't provided, generate a sensible default based on business/mobile
    if not email and mobile:
        email = f"user_{mobile[-4:]}@finmatch.local"

    try:
        user = service.register_business(
            business_name=str(bname or ""),
            owner_name=str(oname or ""),
            email=str(email or ""),
            mobile=str(mobile or ""),
            password=str(password or ""),
            role=role,
        )
        return JSONResponse({"ok": True, "user": user.to_dict()})
    except ValueError as ve:
        return JSONResponse({"ok": False, "error": str(ve)}, status_code=400)
    except Exception as exc:
        return JSONResponse({"ok": False, "error": f"Internal error: {str(exc)}"}, status_code=500)


async def api_get_businesses(request: Request) -> JSONResponse:
    users = service.list_businesses(role="user")
    return JSONResponse({"ok": True, "businesses": [u.to_dict() for u in users]})


async def api_set_business_status(request: Request) -> JSONResponse:
    try:
        data = await request.json()
        uid = data.get("user_id")
        status = data.get("status")
        service.set_business_status(user_id=uid, status=status)
        return JSONResponse({"ok": True, "message": f"Business {uid} set to {status}."})
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=400)


# Define Routes
frontend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend", "finmatch")

routes = [
    Route("/api/health", api_health, methods=["GET"]),
    Route("/api/login", api_login, methods=["POST"]),
    Route("/api/register", api_register, methods=["POST"]),
    Route("/api/businesses", api_get_businesses, methods=["GET"]),
    Route("/api/business/status", api_set_business_status, methods=["POST"]),
]

# Mount frontend directory if it exists
if os.path.exists(frontend_dir):
    routes.append(Mount("/", app=StaticFiles(directory=frontend_dir, html=True), name="frontend"))

middleware = [
    Middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
]

app = Starlette(routes=routes, middleware=middleware)

if __name__ == "__main__":
    import uvicorn

    print("================================================================")
    print("  FinMatch Server Starting at http://localhost:8000")
    print("  - Web Frontend: http://localhost:8000/index.html")
    print("  - Login API:    http://localhost:8000/api/login")
    print("  - Register API: http://localhost:8000/api/register")
    print("================================================================")
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=False)
