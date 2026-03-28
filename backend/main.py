"""FastAPI main application for AppCrawler."""

import asyncio
import json
import logging
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from config import OUTPUT_DIR
from models import CrawlRequest, CrawlStatusResponse, CrawlEvent, ScreenshotInfo
from crawler import create_session, get_session, get_all_sessions
from emulator import (
    get_connected_devices, list_avds, install_apk,
    get_installed_packages, wait_for_device,
)

# ── Logging ────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# ── App ────────────────────────────────────────────────────────────
app = FastAPI(
    title="AppCrawler",
    description="AI-Powered Mobile App Screenshot Crawler",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve screenshots directory
OUTPUT_DIR.mkdir(exist_ok=True)

# ── WebSocket connections ──────────────────────────────────────────
_ws_connections: dict[str, list[WebSocket]] = {}


async def _broadcast(crawl_id: str, event: CrawlEvent):
    """Broadcast a crawl event to all WebSocket clients for a session."""
    clients = _ws_connections.get(crawl_id, [])
    dead = []
    for ws in clients:
        try:
            await ws.send_text(event.model_dump_json())
        except Exception:
            dead.append(ws)
    for ws in dead:
        clients.remove(ws)


# ── REST API ───────────────────────────────────────────────────────

@app.get("/api/health")
async def health_check():
    return {"status": "ok", "service": "AppCrawler"}


@app.get("/api/devices")
async def list_devices():
    """List connected Android devices/emulators."""
    devices = await get_connected_devices()
    avds = await list_avds()
    return {"devices": devices, "avds": avds}


@app.get("/api/devices/{serial}/packages")
async def device_packages(serial: str):
    """List installed packages on a device."""
    packages = await get_installed_packages(serial)
    return {"packages": packages}


@app.post("/api/crawl/start")
async def start_crawl(request: CrawlRequest):
    """Start a new crawl session."""
    # Resolve device
    device_serial = request.device_serial
    if not device_serial:
        try:
            device_serial = await wait_for_device(timeout=10)
        except TimeoutError:
            raise HTTPException(status_code=503, detail="No Android device/emulator found. Please start one first.")

    package_name = request.package_name
    if not package_name and request.play_store_url:
        # Try to extract package name from Play Store URL
        # e.g. https://play.google.com/store/apps/details?id=com.example.app
        import re
        match = re.search(r"id=([a-zA-Z0-9_.]+)", request.play_store_url)
        if match:
            package_name = match.group(1)

    if not package_name:
        raise HTTPException(status_code=400, detail="Package name or Play Store URL required")

    # Create session with broadcast callback
    session = create_session(
        package_name=package_name,
        device_serial=device_serial,
        max_steps=request.max_steps,
        event_callback=lambda evt: _broadcast(session.crawl_id, evt),
    )

    # Start crawl in background
    asyncio.create_task(session.start())

    return {"crawl_id": session.crawl_id, "status": "started", "package_name": package_name}


@app.post("/api/crawl/{crawl_id}/stop")
async def stop_crawl(crawl_id: str):
    """Stop a running crawl."""
    session = get_session(crawl_id)
    if not session:
        raise HTTPException(status_code=404, detail="Crawl session not found")
    session.stop()
    return {"status": "stopped"}


@app.post("/api/crawl/{crawl_id}/pause")
async def pause_crawl(crawl_id: str):
    """Pause a running crawl."""
    session = get_session(crawl_id)
    if not session:
        raise HTTPException(status_code=404, detail="Crawl session not found")
    await session.pause()
    return {"status": "paused"}


@app.post("/api/crawl/{crawl_id}/resume")
async def resume_crawl(crawl_id: str):
    """Resume a paused crawl."""
    session = get_session(crawl_id)
    if not session:
        raise HTTPException(status_code=404, detail="Crawl session not found")
    await session.resume()
    return {"status": "resumed"}


@app.get("/api/crawl/{crawl_id}/status")
async def crawl_status(crawl_id: str):
    """Get crawl session status."""
    session = get_session(crawl_id)
    if not session:
        raise HTTPException(status_code=404, detail="Crawl session not found")
    return session.get_status().model_dump()


@app.get("/api/crawl/{crawl_id}/screenshots")
async def crawl_screenshots(crawl_id: str):
    """Get all screenshots for a crawl session."""
    session = get_session(crawl_id)
    if not session:
        raise HTTPException(status_code=404, detail="Crawl session not found")
    return {"screenshots": [s.model_dump() for s in session.screenshots]}


@app.get("/api/crawl/{crawl_id}/screenshot/{filename}")
async def get_screenshot(crawl_id: str, filename: str):
    """Serve a screenshot file."""
    session = get_session(crawl_id)
    if not session:
        raise HTTPException(status_code=404, detail="Crawl session not found")
    filepath = session.screenshots_dir / filename
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="Screenshot not found")
    return FileResponse(str(filepath), media_type="image/png")


@app.get("/api/crawls")
async def list_crawls():
    """List all crawl sessions."""
    sessions = get_all_sessions()
    return {"crawls": [s.get_status().model_dump() for s in sessions]}


@app.post("/api/upload-apk")
async def upload_apk(file: UploadFile = File(...), device_serial: Optional[str] = None):
    """Upload and install an APK on the device."""
    if not file.filename or not file.filename.endswith(".apk"):
        raise HTTPException(status_code=400, detail="File must be an APK")

    # Save APK
    apk_dir = OUTPUT_DIR / "apks"
    apk_dir.mkdir(exist_ok=True)
    apk_path = apk_dir / file.filename
    content = await file.read()
    apk_path.write_bytes(content)

    # Install on device
    if not device_serial:
        try:
            device_serial = await wait_for_device(timeout=10)
        except TimeoutError:
            raise HTTPException(status_code=503, detail="No device found")

    success = await install_apk(device_serial, str(apk_path))
    if not success:
        raise HTTPException(status_code=500, detail="APK installation failed")

    return {"status": "installed", "path": str(apk_path), "device": device_serial}


# ── WebSocket ──────────────────────────────────────────────────────

@app.websocket("/ws/crawl/{crawl_id}")
async def websocket_crawl(websocket: WebSocket, crawl_id: str):
    """WebSocket endpoint for real-time crawl updates."""
    await websocket.accept()

    if crawl_id not in _ws_connections:
        _ws_connections[crawl_id] = []
    _ws_connections[crawl_id].append(websocket)

    logger.info("WebSocket client connected for crawl %s", crawl_id)

    try:
        # Send current status immediately
        session = get_session(crawl_id)
        if session:
            status = session.get_status()
            await websocket.send_text(
                CrawlEvent(event="status", data=status.model_dump()).model_dump_json()
            )

        # Keep connection alive
        while True:
            try:
                msg = await asyncio.wait_for(websocket.receive_text(), timeout=30)
                # Handle ping/pong or commands
                if msg == "ping":
                    await websocket.send_text(json.dumps({"event": "pong"}))
            except asyncio.TimeoutError:
                # Send keepalive
                await websocket.send_text(json.dumps({"event": "ping"}))

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected for crawl %s", crawl_id)
    finally:
        if crawl_id in _ws_connections:
            try:
                _ws_connections[crawl_id].remove(websocket)
            except ValueError:
                pass


# ── Entry point ────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
