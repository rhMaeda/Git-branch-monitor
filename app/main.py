from __future__ import annotations

import hashlib
import hmac
import logging
from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .config import settings
from .db import get_dashboard_payload, init_db, save_webhook_event
from .sync_service import process_push_webhook, sync_all_branches

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler(timezone="UTC")
templates = Jinja2Templates(directory="app/templates")


def verify_signature(body: bytes, signature_header: str | None) -> bool:
    if not settings.webhook_secret:
        return True
    if not signature_header:
        return False
    expected = "sha256=" + hmac.new(
        settings.webhook_secret.encode("utf-8"),
        body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature_header)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()

    if settings.scheduled_sync_enabled:
        scheduler.add_job(sync_all_branches, "interval", minutes=settings.scheduled_sync_minutes, id="scheduled_sync", replace_existing=True)
        scheduler.start()
        logger.info("Scheduled sync enabled: every %s minutes", settings.scheduled_sync_minutes)

    if settings.sync_on_startup:
        try:
            sync_all_branches()
        except Exception as exc:
            logger.exception("Initial sync failed: %s", exc)

    yield

    if scheduler.running:
        scheduler.shutdown(wait=False)


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "app_name": settings.app_name,
            "repo": settings.repo_full_name,
            "branches": settings.monitored_branches,
            "base_branch": settings.default_compare_base,
        },
    )


@app.get("/api/dashboard")
async def dashboard_data():
    return JSONResponse(get_dashboard_payload())


@app.post("/api/sync")
async def manual_sync():
    return JSONResponse(sync_all_branches())


@app.post("/api/github/webhook")
async def github_webhook(request: Request):
    body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256")
    if not verify_signature(body, signature):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    event_name = request.headers.get("X-GitHub-Event", "unknown")
    delivery_id = request.headers.get("X-GitHub-Delivery", "")
    payload = await request.json()

    if delivery_id and not save_webhook_event(delivery_id, event_name, payload):
        return JSONResponse({"ok": True, "duplicate": True})

    if event_name == "ping":
        return JSONResponse({"ok": True, "message": "pong"})

    if event_name != "push":
        return JSONResponse({"ok": True, "ignored": True, "event": event_name})

    result = process_push_webhook(payload)
    return JSONResponse({"ok": True, "result": result})
