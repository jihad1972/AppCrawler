"""Core AI-driven crawling engine for Android apps."""

import asyncio
import logging
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Callable, Awaitable

import imagehash
from PIL import Image
from appium import webdriver as appium_webdriver
from appium.options.android import UiAutomator2Options

from config import (
    APPIUM_HOST, DEFAULT_MAX_STEPS, SCREENSHOT_DELAY,
    HASH_SIMILARITY_THRESHOLD, OUTPUT_DIR,
)
from models import (
    ActionDecision, ActionType, CrawlStatusEnum,
    CrawlStatusResponse, ScreenshotInfo, CrawlEvent,
)
from ai_vision import analyze_screen
from emulator import (
    wait_for_device, wait_for_boot, launch_app,
    get_screen_resolution,
)

logger = logging.getLogger(__name__)


class CrawlSession:
    """Manages a single app crawling session."""

    def __init__(
        self,
        crawl_id: str,
        package_name: str,
        device_serial: str,
        max_steps: int = DEFAULT_MAX_STEPS,
        event_callback: Optional[Callable[[CrawlEvent], Awaitable[None]]] = None,
    ):
        self.crawl_id = crawl_id
        self.package_name = package_name
        self.device_serial = device_serial
        self.max_steps = max_steps
        self._event_callback = event_callback

        # State
        self.status = CrawlStatusEnum.PENDING
        self.steps_taken = 0
        self.screenshots: list[ScreenshotInfo] = []
        self.screen_hashes: list[imagehash.ImageHash] = []
        self.visited_labels: list[str] = []
        self.recent_actions: list[str] = []
        self.error: Optional[str] = None
        self._stop_requested = False

        # Phase 1: Pause/Resume via asyncio.Event
        self._pause_event = asyncio.Event()
        self._pause_event.set()  # Not paused by default (set = running)

        # Phase 1: ETA tracking
        self._started_at: Optional[float] = None
        self._step_durations: list[float] = []

        # Appium driver
        self._driver: Optional[appium_webdriver.Remote] = None

        # Output directory
        self.session_dir = OUTPUT_DIR / f"crawl_{crawl_id}"
        self.screenshots_dir = self.session_dir / "screenshots"
        self.screenshots_dir.mkdir(parents=True, exist_ok=True)

        # Screen resolution
        self.screen_w = 1080
        self.screen_h = 1920

    # ── Public API ────────────────────────────────────────────────

    async def start(self):
        """Run the full crawl pipeline."""
        try:
            self.status = CrawlStatusEnum.STARTING
            self._started_at = time.monotonic()
            await self._emit("status", {
                "status": self.status.value,
                "message": "Initializing...",
                "started_at": datetime.now(timezone.utc).isoformat(),
            })

            # Connect Appium
            await self._connect_appium()
            self.screen_w, self.screen_h = await get_screen_resolution(self.device_serial)

            # Launch the app
            await launch_app(self.device_serial, self.package_name)
            await asyncio.sleep(3)  # Wait for app to fully launch

            self.status = CrawlStatusEnum.RUNNING
            await self._emit("status", {"status": self.status.value, "message": "Crawling..."})

            # Main crawl loop
            await self._crawl_loop()

            if not self._stop_requested:
                self.status = CrawlStatusEnum.COMPLETED
                await self._emit("complete", {
                    "status": self.status.value,
                    "total_steps": self.steps_taken,
                    "unique_screens": len(set(self.visited_labels)),
                    "total_screenshots": len(self.screenshots),
                    "elapsed_seconds": self._elapsed(),
                })

        except Exception as e:
            logger.exception("Crawl session failed")
            self.status = CrawlStatusEnum.FAILED
            self.error = str(e)
            await self._emit("error", {"error": str(e)})
        finally:
            await self._disconnect_appium()

    def stop(self):
        """Request the crawl to stop."""
        self._stop_requested = True
        self.status = CrawlStatusEnum.STOPPED
        # Unpause if paused so the loop can exit
        self._pause_event.set()

    async def pause(self):
        """Pause the crawl."""
        if self.status == CrawlStatusEnum.RUNNING:
            self._pause_event.clear()  # Block the loop
            self.status = CrawlStatusEnum.PAUSED
            await self._emit("paused", {
                "status": self.status.value,
                "message": "Crawl paused",
                "steps_taken": self.steps_taken,
                "elapsed_seconds": self._elapsed(),
            })

    async def resume(self):
        """Resume a paused crawl."""
        if self.status == CrawlStatusEnum.PAUSED:
            self.status = CrawlStatusEnum.RUNNING
            self._pause_event.set()  # Unblock the loop
            await self._emit("resumed", {
                "status": self.status.value,
                "message": "Crawl resumed",
                "steps_taken": self.steps_taken,
            })

    def get_status(self) -> CrawlStatusResponse:
        """Return current status."""
        avg_dur = self._avg_step_duration()
        remaining = self.max_steps - self.steps_taken
        eta = avg_dur * remaining if avg_dur and remaining > 0 else None

        return CrawlStatusResponse(
            crawl_id=self.crawl_id,
            status=self.status,
            package_name=self.package_name,
            steps_taken=self.steps_taken,
            max_steps=self.max_steps,
            unique_screens=len(set(self.visited_labels)),
            current_screen=self.visited_labels[-1] if self.visited_labels else None,
            error=self.error,
            eta_seconds=round(eta, 1) if eta else None,
            avg_step_duration=round(avg_dur, 2) if avg_dur else None,
            elapsed_seconds=round(self._elapsed(), 1) if self._started_at else None,
            started_at=datetime.fromtimestamp(
                time.time() - (time.monotonic() - self._started_at), tz=timezone.utc
            ).isoformat() if self._started_at else None,
        )

    # ── ETA helpers ───────────────────────────────────────────────

    def _elapsed(self) -> float:
        return time.monotonic() - self._started_at if self._started_at else 0.0

    def _avg_step_duration(self) -> Optional[float]:
        if not self._step_durations:
            return None
        # Weighted recent average (last 10 matter more)
        recent = self._step_durations[-10:]
        return sum(recent) / len(recent)

    # ── Appium connection ─────────────────────────────────────────

    async def _connect_appium(self):
        """Connect to Appium server."""
        options = UiAutomator2Options()
        options.platform_name = "Android"
        options.device_name = self.device_serial
        options.udid = self.device_serial
        options.no_reset = True
        options.auto_grant_permissions = True
        options.new_command_timeout = 300

        logger.info("Connecting to Appium at %s for device %s", APPIUM_HOST, self.device_serial)

        loop = asyncio.get_event_loop()
        self._driver = await loop.run_in_executor(
            None,
            lambda: appium_webdriver.Remote(APPIUM_HOST, options=options),
        )
        logger.info("Appium connected successfully")

    async def _disconnect_appium(self):
        """Disconnect from Appium."""
        if self._driver:
            try:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, self._driver.quit)
            except Exception:
                pass
            self._driver = None

    # ── Main crawl loop ───────────────────────────────────────────

    async def _crawl_loop(self):
        """Core exploration loop with pause/resume support."""
        consecutive_duplicates = 0

        for step in range(self.max_steps):
            # Check pause — will block here if paused
            await self._pause_event.wait()

            if self._stop_requested:
                break

            step_start = time.monotonic()
            self.steps_taken = step + 1

            # 1. Take screenshot
            screenshot_path = self.screenshots_dir / f"step_{step:04d}.png"
            await self._take_screenshot(str(screenshot_path))

            # 2. Screen-settle detection: wait for screen to stabilize
            settled = await self._wait_for_screen_settle(str(screenshot_path))
            if settled:
                # Retake screenshot after settle if it changed
                await self._take_screenshot(str(screenshot_path))

            # 3. Check for duplicate screen
            is_duplicate = self._is_duplicate_screen(str(screenshot_path))
            if is_duplicate:
                consecutive_duplicates += 1
                if consecutive_duplicates >= 5:
                    logger.info("Too many consecutive duplicates, stopping")
                    break
            else:
                consecutive_duplicates = 0

            # 4. Ask AI what to do
            action, screen_label = await analyze_screen(
                str(screenshot_path),
                self.visited_labels,
                self.recent_actions,
            )

            self.visited_labels.append(screen_label)

            # 5. Record screenshot info
            info = ScreenshotInfo(
                filename=screenshot_path.name,
                step_number=step,
                timestamp=datetime.now(timezone.utc).isoformat(),
                screen_label=screen_label,
                action_taken=f"{action.action.value}" if action else "none",
                ai_reasoning=action.reasoning if action else "",
                is_duplicate=is_duplicate,
            )
            self.screenshots.append(info)

            # 6. Track step duration for ETA
            step_duration = time.monotonic() - step_start
            self._step_durations.append(step_duration)
            avg_dur = self._avg_step_duration()
            remaining = self.max_steps - self.steps_taken
            eta = avg_dur * remaining if avg_dur else None

            # 7. Emit events
            await self._emit("screenshot", {
                "filename": info.filename,
                "step": step,
                "screen_label": screen_label,
                "is_duplicate": is_duplicate,
            })
            await self._emit("step", {
                "step": step,
                "total": self.max_steps,
                "action": action.action.value if action else "none",
                "reasoning": action.reasoning if action else "",
                "element": action.element_description if action else "",
                "screen_label": screen_label,
                "unique_screens": len(set(self.visited_labels)),
                "eta_seconds": round(eta, 1) if eta else None,
                "avg_step_duration": round(avg_dur, 2) if avg_dur else None,
                "elapsed_seconds": round(self._elapsed(), 1),
            })

            if action is None:
                logger.warning("AI returned no action at step %d, pressing back", step)
                await self._execute_action(ActionDecision(action=ActionType.BACK, reasoning="Fallback"))
                continue

            # 8. Execute the action
            self.recent_actions.append(
                f"Step {step}: {action.action.value} → {action.element_description}"
            )
            await self._execute_action(action)

            # 9. Wait for screen to settle
            await asyncio.sleep(SCREENSHOT_DELAY)

    # ── Screenshot & hashing ──────────────────────────────────────

    async def _take_screenshot(self, path: str):
        """Take a screenshot via Appium."""
        loop = asyncio.get_event_loop()
        png_data = await loop.run_in_executor(None, self._driver.get_screenshot_as_png)
        Path(path).write_bytes(png_data)

    async def _wait_for_screen_settle(self, path: str, max_checks: int = 3, interval: float = 0.5) -> bool:
        """
        Wait until the screen stops changing (animations finished).
        Takes a second screenshot and compares pHash; repeats up to max_checks.
        Returns True if the screen changed and was re-captured.
        """
        try:
            prev_hash = imagehash.phash(Image.open(path))
            changed = False

            for _ in range(max_checks):
                await asyncio.sleep(interval)
                tmp_path = path + ".tmp.png"
                await self._take_screenshot(tmp_path)
                curr_hash = imagehash.phash(Image.open(tmp_path))

                if abs(prev_hash - curr_hash) <= 2:
                    # Screen has settled
                    Path(tmp_path).unlink(missing_ok=True)
                    return changed

                # Screen still changing
                prev_hash = curr_hash
                changed = True
                # Overwrite with latest
                Path(tmp_path).replace(path)

            return changed
        except Exception as e:
            logger.warning("Screen settle check failed: %s", e)
            return False

    def _is_duplicate_screen(self, path: str) -> bool:
        """Check if this screenshot is similar to a previously seen one (pHash)."""
        try:
            img = Image.open(path)
            h = imagehash.phash(img)
            for existing in self.screen_hashes:
                if abs(h - existing) < HASH_SIMILARITY_THRESHOLD:
                    return True
            self.screen_hashes.append(h)
            return False
        except Exception:
            return False

    # ── Action execution ──────────────────────────────────────────

    async def _execute_action(self, action: ActionDecision):
        """Execute an action on the device via Appium."""
        loop = asyncio.get_event_loop()

        try:
            if action.action == ActionType.TAP and action.x is not None and action.y is not None:
                await loop.run_in_executor(
                    None,
                    lambda: self._driver.tap([(action.x, action.y)]),
                )
            elif action.action == ActionType.SWIPE_UP:
                await loop.run_in_executor(
                    None,
                    lambda: self._driver.swipe(
                        self.screen_w // 2, int(self.screen_h * 0.7),
                        self.screen_w // 2, int(self.screen_h * 0.3),
                        800,
                    ),
                )
            elif action.action == ActionType.SWIPE_DOWN:
                await loop.run_in_executor(
                    None,
                    lambda: self._driver.swipe(
                        self.screen_w // 2, int(self.screen_h * 0.3),
                        self.screen_w // 2, int(self.screen_h * 0.7),
                        800,
                    ),
                )
            elif action.action == ActionType.SWIPE_LEFT:
                await loop.run_in_executor(
                    None,
                    lambda: self._driver.swipe(
                        int(self.screen_w * 0.8), self.screen_h // 2,
                        int(self.screen_w * 0.2), self.screen_h // 2,
                        800,
                    ),
                )
            elif action.action == ActionType.SWIPE_RIGHT:
                await loop.run_in_executor(
                    None,
                    lambda: self._driver.swipe(
                        int(self.screen_w * 0.2), self.screen_h // 2,
                        int(self.screen_w * 0.8), self.screen_h // 2,
                        800,
                    ),
                )
            elif action.action == ActionType.BACK:
                await loop.run_in_executor(None, self._driver.back)
            elif action.action == ActionType.TYPE_TEXT and action.text:
                if action.x is not None and action.y is not None:
                    await loop.run_in_executor(
                        None,
                        lambda: self._driver.tap([(action.x, action.y)]),
                    )
                    await asyncio.sleep(0.5)
                from emulator import _run, ADB_PATH
                text = action.text.replace(" ", "%s").replace("'", "\\'")
                await _run([ADB_PATH, "-s", self.device_serial, "shell", "input", "text", text])
            elif action.action == ActionType.HOME:
                await loop.run_in_executor(
                    None,
                    lambda: self._driver.press_keycode(3),
                )
            else:
                await asyncio.sleep(1)

        except Exception as e:
            logger.warning("Action execution failed: %s", e)

    # ── Event emission ────────────────────────────────────────────

    async def _emit(self, event: str, data: dict):
        """Emit a crawl event to the WebSocket callback."""
        evt = CrawlEvent(event=event, data=data)
        if self._event_callback:
            try:
                await self._event_callback(evt)
            except Exception:
                pass


# ── Session manager ───────────────────────────────────────────────

_sessions: dict[str, CrawlSession] = {}


def create_session(
    package_name: str,
    device_serial: str,
    max_steps: int = DEFAULT_MAX_STEPS,
    event_callback: Optional[Callable[[CrawlEvent], Awaitable[None]]] = None,
) -> CrawlSession:
    """Create and register a new crawl session."""
    crawl_id = uuid.uuid4().hex[:12]
    session = CrawlSession(
        crawl_id=crawl_id,
        package_name=package_name,
        device_serial=device_serial,
        max_steps=max_steps,
        event_callback=event_callback,
    )
    _sessions[crawl_id] = session
    return session


def get_session(crawl_id: str) -> Optional[CrawlSession]:
    """Get a session by ID."""
    return _sessions.get(crawl_id)


def get_all_sessions() -> list[CrawlSession]:
    """Get all sessions."""
    return list(_sessions.values())
