"""Pydantic models for AppCrawler API."""

from __future__ import annotations
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


# ── Enums ──────────────────────────────────────────────────────────

class CrawlStatusEnum(str, Enum):
    PENDING = "pending"
    STARTING = "starting"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    STOPPED = "stopped"


class ActionType(str, Enum):
    TAP = "tap"
    SWIPE_UP = "swipe_up"
    SWIPE_DOWN = "swipe_down"
    SWIPE_LEFT = "swipe_left"
    SWIPE_RIGHT = "swipe_right"
    BACK = "back"
    TYPE_TEXT = "type_text"
    HOME = "home"
    WAIT = "wait"


# ── Request / Response Models ──────────────────────────────────────

class CrawlRequest(BaseModel):
    """Start a new crawl session."""
    package_name: Optional[str] = Field(None, description="Android package name, e.g. com.google.android.calculator")
    play_store_url: Optional[str] = Field(None, description="Play Store URL to resolve package name")
    max_steps: int = Field(40, ge=5, le=200, description="Maximum exploration steps")
    device_serial: Optional[str] = Field(None, description="ADB device serial (auto-detect if omitted)")


class CrawlStatusResponse(BaseModel):
    """Status of a crawl session."""
    crawl_id: str
    status: CrawlStatusEnum
    package_name: str = ""
    steps_taken: int = 0
    max_steps: int = 40
    unique_screens: int = 0
    current_screen: Optional[str] = None
    error: Optional[str] = None
    # Phase 1: ETA & timing
    eta_seconds: Optional[float] = None
    avg_step_duration: Optional[float] = None
    elapsed_seconds: Optional[float] = None
    started_at: Optional[str] = None


class ScreenshotInfo(BaseModel):
    """Metadata for a captured screenshot."""
    filename: str
    step_number: int
    timestamp: str
    screen_label: str = ""
    action_taken: str = ""
    ai_reasoning: str = ""
    is_duplicate: bool = False
    width: int = 0
    height: int = 0


class ActionDecision(BaseModel):
    """AI-decided action to perform on the device."""
    action: ActionType
    x: Optional[int] = None
    y: Optional[int] = None
    text: Optional[str] = None
    reasoning: str = ""
    element_description: str = ""


class CrawlEvent(BaseModel):
    """WebSocket event sent to the frontend."""
    event: str  # "step", "screenshot", "status", "error", "complete", "paused", "resumed"
    data: dict = {}
