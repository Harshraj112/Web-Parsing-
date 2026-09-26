import json
import os
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from models.notification import (
    JobPayload,
    NotificationRequest,
    NotificationResponse
)

APP_DIR = Path(__file__).resolve().parent
load_dotenv(APP_DIR / ".env")

from services.telegram_service import TelegramService
from services.whatsapp_service import WhatsAppService
from services.notification_service import NotificationService


# Load .env
load_dotenv()


# Read environment variables
TELEGRAM_BOT_TOKEN = (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
WHATSAPP_ACCESS_TOKEN = (os.getenv("WHATSAPP_ACCESS_TOKEN") or "").strip()
WHATSAPP_PHONE_NUMBER_ID = (os.getenv("WHATSAPP_PHONE_NUMBER_ID") or "").strip()
WHATSAPP_GRAPH_API_VERSION = (os.getenv("WHATSAPP_GRAPH_API_VERSION", "v26.0") or "v26.0").strip()


# Validate configuration
if not TELEGRAM_BOT_TOKEN:
    raise RuntimeError(
        "TELEGRAM_BOT_TOKEN is not configured"
    )

if not WHATSAPP_ACCESS_TOKEN:
    raise RuntimeError(
        "WHATSAPP_ACCESS_TOKEN is not configured"
    )

if not WHATSAPP_PHONE_NUMBER_ID:
    raise RuntimeError(
        "WHATSAPP_PHONE_NUMBER_ID is not configured"
    )


ROOT_DIR = Path(__file__).resolve().parents[1]
JOB_QUEUE_PATH = ROOT_DIR / "output" / "india_jobs.json"
SCRAPE_SCRIPT_PATH = ROOT_DIR / "scrape_india_jobs.py"
SCRAPE_INTERVAL_SECONDS = 2 * 24 * 60 * 60


# Create services
telegram_service = TelegramService(
    TELEGRAM_BOT_TOKEN
)

whatsapp_service = WhatsAppService(
    WHATSAPP_ACCESS_TOKEN,
    WHATSAPP_PHONE_NUMBER_ID,
    WHATSAPP_GRAPH_API_VERSION
)


def get_queue_status() -> dict[str, object]:
    if not JOB_QUEUE_PATH.exists():
        return {
            "jobs_count": 0,
            "last_scrape": None,
            "last_updated_seconds_ago": None,
            "stale": True,
            "next_refresh_seconds": SCRAPE_INTERVAL_SECONDS,
        }

    stat = JOB_QUEUE_PATH.stat()
    now = time.time()
    age_seconds = max(0.0, now - stat.st_mtime)

    try:
        with JOB_QUEUE_PATH.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        jobs_count = len(payload) if isinstance(payload, list) else 0
    except (json.JSONDecodeError, OSError):
        jobs_count = 0

    last_updated = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
    stale = age_seconds >= SCRAPE_INTERVAL_SECONDS

    return {
        "jobs_count": jobs_count,
        "last_scrape": last_updated,
        "last_updated_seconds_ago": round(age_seconds, 2),
        "stale": stale,
        "next_refresh_seconds": max(0, int(SCRAPE_INTERVAL_SECONDS - age_seconds)),
    }


def run_scrape_job(force: bool = False) -> bool:
    if JOB_QUEUE_PATH.exists() and not force:
        status = get_queue_status()
        if status["stale"] is False:
            print("[Scheduler] queue is fresh; skipping scraper refresh")
            return True

    print("[Scheduler] queue is stale or missing; running scrape_india_jobs.py")
    try:
        result = subprocess.run(
            [sys.executable, str(SCRAPE_SCRIPT_PATH)],
            cwd=str(ROOT_DIR),
            capture_output=True,
            text=True,
            timeout=1800,
        )
    except subprocess.TimeoutExpired as exc:
        print(f"[Scheduler] scrape timed out: {exc}")
        return False

    if result.stdout:
        print(result.stdout.strip())
    if result.stderr:
        print(result.stderr.strip())

    if result.returncode != 0:
        print(f"[Scheduler] scrape failed with exit code {result.returncode}")
        return False

    print("[Scheduler] scrape finished successfully")
    return True


def start_background_scraper() -> None:
    def loop() -> None:
        run_scrape_job(force=True)
        while True:
            time.sleep(SCRAPE_INTERVAL_SECONDS)
            run_scrape_job()

    worker = threading.Thread(target=loop, daemon=True)
    worker.start()


def load_next_jobs_from_queue(batch_size: int = 5) -> list[JobPayload]:
    queue_path = Path(__file__).resolve().parents[1] / "output" / "india_jobs.json"
    if not queue_path.exists():
        return []

    try:
        with queue_path.open("r", encoding="utf-8") as handle:
            records = json.load(handle)
    except (json.JSONDecodeError, OSError) as exc:
        print(f"[API] failed reading queue file: {exc}")
        return []

    if not isinstance(records, list):
        return []

    batch_size = max(1, min(batch_size, 10))
    batch = records[:batch_size]
    remaining = records[batch_size:]

    try:
        with queue_path.open("w", encoding="utf-8") as handle:
            json.dump(remaining, handle, ensure_ascii=False, indent=2)
    except OSError as exc:
        print(f"[API] failed updating queue file: {exc}")

    parsed_jobs: list[JobPayload] = []
    for record in batch:
        if not isinstance(record, dict):
            continue
        parsed_jobs.append(JobPayload(**record))

    return parsed_jobs


notification_service = NotificationService(
    telegram_service,
    whatsapp_service
)

start_background_scraper()


# Create FastAPI application
app = FastAPI(
    title="Notification Service",
    description="Telegram and WhatsApp Notification Service",
    version="1.0.0"
)


@app.middleware("http")
async def normalize_human_handles(request: Request, call_next):
    if request.method in {"POST", "PUT", "PATCH"} and request.url.path in {
        "/api/notifications/send",
        "/api/notifications/send-jobs",
    }:
        try:
            body = await request.body()
            if not body:
                return await call_next(request)

            payload = json.loads(body)
            if not isinstance(payload, dict):
                return await call_next(request)

            if "channel" in payload and isinstance(payload["channel"], str):
                payload["channel"] = payload["channel"].strip().lower()

            recipient = payload.get("recipient")
            handle = payload.get("handle")
            if isinstance(handle, str) and (recipient is None or str(recipient).strip() == ""):
                payload["recipient"] = handle.strip()

            if isinstance(recipient, str):
                payload["recipient"] = recipient.strip()

            if isinstance(payload.get("recipient"), str):
                value = payload["recipient"].strip()
                if value.startswith("@"):
                    payload["recipient"] = value
                elif value:
                    payload["recipient"] = value
                print(f"[Middleware] normalized recipient={payload['recipient']}")

            request._body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        except Exception:
            pass

    return await call_next(request)


@app.get("/api/notifications/health")
async def health():
    queue_status = get_queue_status()
    return {
        "status": "UP",
        "service": "notification-service",
        "jobs_count": queue_status["jobs_count"],
        "last_scrape": queue_status["last_scrape"],
        "stale": queue_status["stale"],
        "next_refresh_seconds": queue_status["next_refresh_seconds"],
    }


@app.post(
    "/api/notifications/send",
    response_model=NotificationResponse
)
async def send_notification(
    request: NotificationRequest
):

    channel = request.channel.strip().lower()

    if channel not in ["telegram", "whatsapp"]:

        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "channel": channel,
                "message": (
                    "Unsupported channel. "
                    "Use telegram or whatsapp."
                )
            }
        )

    success = await notification_service.send(request)

    if success:

        return NotificationResponse(
            success=True,
            channel=channel,
            message="Notification sent successfully",
            jobs_sent=len(request.jobs) if request.jobs else 0,
        )

    return JSONResponse(
        status_code=502,
        content={
            "success": False,
            "channel": channel,
            "message": "Notification provider failed"
        }
    )


@app.post(
    "/api/notifications/send-jobs",
    response_model=NotificationResponse
)
async def send_jobs_notification(
    request: NotificationRequest
):
    print(f"[API] /api/notifications/send-jobs called: channel={request.channel}, recipient={request.recipient}, jobs={len(request.jobs)}")

    if not request.jobs:
        queue_jobs = load_next_jobs_from_queue(batch_size=5)
        if queue_jobs:
            request.jobs = queue_jobs
            print(f"[API] loaded {len(request.jobs)} jobs from output/india_jobs.json")
        else:
            print("[API] no jobs provided and no queue entries found; returning 400")
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "channel": request.channel,
                    "message": "No jobs provided to send."
                }
            )

    request.message = notification_service._format_jobs_message(request.jobs)
    print(f"[API] formatted jobs message length={len(request.message)}")
    success = await notification_service.send(request)

    if success:
        print(f"[API] success for {request.channel}")
        return NotificationResponse(
            success=True,
            channel=request.channel,
            message="Jobs sent successfully",
            jobs_sent=len(request.jobs),
        )

    print(f"[API] failed for {request.channel}")
    return JSONResponse(
        status_code=502,
        content={
            "success": False,
            "channel": request.channel,
            "message": "Notification provider failed"
        }
    )