import os, logging, asyncio, uuid, time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, Depends, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse, Response
from fastapi.staticfiles import StaticFiles
from flet_fastapi import FletApp
from starlette.middleware.base import BaseHTTPMiddleware

from config import settings
from database import get_engine, get_session_maker, Base, check_ai_limit, log_ai_usage
from auth import router as auth_router, get_current_user
from ai_router import get_ai_router
from social import router as social_router
from reels_status import router as reels_status_router
from streaming import router as streaming_router
from meetings import router as meetings_router
from cleanup import cleanup_expired_statuses, cleanup_temp_chunks
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

logging.basicConfig(level=settings.LOG_LEVEL, format="%(asctime)s [%(levelname)s] rid=%(request_id)s %(message)s")
logger = logging.getLogger("echochat")

class RequestIDFilter(logging.Filter):
    def filter(self, record):
        record.request_id = getattr(record, "request_id", "----")
        return True
logger.addFilter(RequestIDFilter())

async def global_exception_handler(request: Request, exc: Exception):
    request_id = getattr(request.state, "request_id", "unknown")
    logger.exception(f"Unhandled exception: {exc}", extra={"request_id": request_id})
    return JSONResponse(status_code=500, content={"error": "Internal server error", "request_id": request_id})

MAX_BODY_SIZE = 1_000_000
class MaxSizeMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > MAX_BODY_SIZE:
            return JSONResponse(status_code=413, content={"error": "Request body too large"})
        return await call_next(request)

@asynccontextmanager
async def lifespan(app: FastAPI):
    Path(settings.LOCAL_MEDIA_ROOT).mkdir(parents=True, exist_ok=True)
    Path("static").mkdir(exist_ok=True)
    manifest = Path("static/manifest.json")
    if not manifest.exists():
        manifest.write_text('{"name":"EchoChat","short_name":"EchoChat","start_url":"/app","display":"standalone","background_color":"#0F172A","theme_color":"#7C3AED","icons":[{"src":"/media/icon-192.png","sizes":"192x192","type":"image/png"},{"src":"/media/icon-512.png","sizes":"512x512","type":"image/png"}]}')
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database ready")
    tasks = [
        asyncio.create_task(cleanup_expired_statuses()),
        asyncio.create_task(cleanup_temp_chunks()),
    ]
    yield
    for t in tasks:
        t.cancel()
    logger.info("Shutdown complete")

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
    exception_handlers={Exception: global_exception_handler}
)

app.add_middleware(MaxSizeMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request.state.request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    logger.info(f"--> {request.method} {request.url.path}", extra={"request_id": request.state.request_id})
    start = time.time()
    response = await call_next(request)
    duration = time.time() - start
    response.headers["X-Request-ID"] = request.state.request_id
    logger.info(f"<-- {response.status_code} ({duration:.3f}s)", extra={"request_id": request.state.request_id})
    return response

app.include_router(auth_router)
app.include_router(social_router)
app.include_router(reels_status_router)
app.include_router(streaming_router)
app.include_router(meetings_router)

MEDIA_ROOT = Path(settings.LOCAL_MEDIA_ROOT)
encryption_key = bytes.fromhex(settings.MEDIA_ENCRYPTION_KEY)

@app.get("/media/{file_path:path}")
async def serve_media(file_path: str, current_user=Depends(get_current_user)):
    file_location = MEDIA_ROOT / file_path
    if not file_location.exists():
        raise HTTPException(404, "File not found")
    with open(file_location, "rb") as f:
        encrypted_data = f.read()
    if len(encrypted_data) < 12:
        raise HTTPException(500, "Invalid encrypted file")
    nonce, ciphertext = encrypted_data[:12], encrypted_data[12:]
    aesgcm = AESGCM(encryption_key)
    try:
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    except Exception:
        raise HTTPException(500, "Decryption failed")
    return Response(content=plaintext, media_type="application/octet-stream")

@app.post("/chat")
async def chat(
    message: str = Form(...),
    user_id: str = Form(...),
    current_user=Depends(get_current_user),
    ai_router=Depends(get_ai_router),
):
    if not message.strip():
        raise HTTPException(400, "Message cannot be empty")
    async with get_session_maker()() as db:
        if not await check_ai_limit(current_user.id, db):
            raise HTTPException(429, "Daily AI limit reached")
        try:
            result = await asyncio.wait_for(ai_router.route_message(message, user_id), timeout=20)
            await log_ai_usage(db, current_user.id)
            return result
        except asyncio.TimeoutError:
            raise HTTPException(504, "AI service timeout")

@app.post("/chat/stream")
async def chat_stream(
    message: str = Form(...),
    user_id: str = Form(...),
    current_user=Depends(get_current_user),
    ai_router=Depends(get_ai_router),
):
    if not message.strip():
        raise HTTPException(400, "Message cannot be empty")
    async with get_session_maker()() as db:
        if not await check_ai_limit(current_user.id, db):
            raise HTTPException(429, "Daily AI limit reached")
        await log_ai_usage(db, current_user.id)
    async def event_generator():
        try:
            async for token in ai_router.route_message_stream(message, user_id):
                yield f"data: {token}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            logger.error(f"Stream error: {e}")
            yield "data: [ERROR]\n\n"
    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.get("/health")
async def health():
    try:
        async with get_session_maker()() as db:
            await db.execute("SELECT 1")
    except Exception:
        return JSONResponse(status_code=503, content={"status": "unhealthy"})
    return {"status": "ok", "app": settings.APP_NAME, "version": settings.APP_VERSION}

from flet_app import build_flet_app
app.mount("/app", FletApp(build_flet_app()))
app.mount("/static", StaticFiles(directory="static"), name="static")
from flet_fastapi import FletApp
from flet_app import build_flet_app

app.mount("/app", FletApp(build_flet_app()))
app.mount("/static", StaticFiles(directory="static"), name="static")
