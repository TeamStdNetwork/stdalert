import hmac
import hashlib
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.webhook.handler import process_webhook, verify_signature
from app.dashboard.routes import router as dashboard_router
from app.billing.routes import router as billing_router

logging.basicConfig(level=settings.LOG_LEVEL)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize scheduler
    logger.info("Initializing scheduler...")
    yield
    # Shutdown scheduler
    logger.info("Shutting down scheduler...")

app = FastAPI(title="STD Alert", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(dashboard_router)
app.include_router(billing_router)

@app.get("/")
async def health_check():
    return {"status": "ok", "version": "1.0.0"}

@app.post("/webhook/github")
async def github_webhook(
    request: Request,
    x_hub_signature_256: str = Header(None),
    x_github_event: str = Header(None)
):
    if not x_hub_signature_256:
        raise HTTPException(status_code=400, detail="Missing signature")
    
    payload = await request.body()
    
    if not verify_signature(payload, x_hub_signature_256, settings.GITHUB_WEBHOOK_SECRET):
        raise HTTPException(status_code=401, detail="Invalid signature")

    event_payload = await request.json()
    logger.info(f"Received GitHub webhook event: {x_github_event}")
    
    await process_webhook(x_github_event, event_payload)
    
    return {"status": "accepted"}

@app.post("/scan/{owner}/{repo}")
async def manual_scan(owner: str, repo: str):
    logger.info(f"Manual scan triggered for {owner}/{repo}")
    # Trigger scan logic here
    return {"status": "scan initiated", "repo": f"{owner}/{repo}"}


@app.post("/webhook/telegram")
async def telegram_webhook(request: Request):
    """Handle incoming Telegram bot updates (commands from users)."""
    if not settings.TELEGRAM_BOT_TOKEN:
        raise HTTPException(status_code=503, detail="Telegram not configured")

    from app.notifications.telegram import TelegramCommandHandler

    update = await request.json()
    handler = TelegramCommandHandler(bot_token=settings.TELEGRAM_BOT_TOKEN)
    await handler.handle_update(update)
    return {"status": "ok"}
