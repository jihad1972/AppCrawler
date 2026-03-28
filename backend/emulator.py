"""Android emulator management via ADB and SDK tools."""

import asyncio
import logging
import re
from typing import Optional

from config import ADB_PATH, EMULATOR_PATH

logger = logging.getLogger(__name__)


async def _run(cmd: list[str], timeout: float = 30) -> tuple[int, str, str]:
    """Run a subprocess and return (returncode, stdout, stderr)."""
    logger.info("Running: %s", " ".join(cmd))
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError:
        logger.warning("Binary not found: %s", cmd[0])
        return -1, "", f"Binary not found: {cmd[0]}"
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        return -1, "", "Timeout"
    return proc.returncode, stdout.decode(errors="replace"), stderr.decode(errors="replace")


# ── ADB helpers ───────────────────────────────────────────────────

async def get_connected_devices() -> list[dict]:
    """Return list of {serial, state} for connected devices/emulators."""
    rc, out, _ = await _run([ADB_PATH, "devices"])
    if rc != 0:
        return []
    devices = []
    for line in out.strip().splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 2:
            devices.append({"serial": parts[0], "state": parts[1]})
    return devices


async def wait_for_device(serial: Optional[str] = None, timeout: float = 120) -> str:
    """Wait until a device is online. Returns serial."""
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        devices = await get_connected_devices()
        online = [d for d in devices if d["state"] == "device"]
        if online:
            if serial:
                match = [d for d in online if d["serial"] == serial]
                if match:
                    return match[0]["serial"]
            else:
                return online[0]["serial"]
        await asyncio.sleep(2)
    raise TimeoutError(f"No device online after {timeout}s")


async def wait_for_boot(serial: str, timeout: float = 180) -> bool:
    """Wait until the emulator is fully booted (sys.boot_completed=1)."""
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        rc, out, _ = await _run(
            [ADB_PATH, "-s", serial, "shell", "getprop", "sys.boot_completed"], timeout=10
        )
        if rc == 0 and out.strip() == "1":
            logger.info("Device %s fully booted", serial)
            return True
        await asyncio.sleep(3)
    return False


async def install_apk(serial: str, apk_path: str) -> bool:
    """Install an APK on the device."""
    rc, out, err = await _run([ADB_PATH, "-s", serial, "install", "-r", apk_path], timeout=120)
    if rc == 0 and "Success" in out:
        logger.info("APK installed successfully on %s", serial)
        return True
    logger.error("APK install failed: %s %s", out, err)
    return False


async def get_installed_packages(serial: str) -> list[str]:
    """List all installed packages on device."""
    rc, out, _ = await _run([ADB_PATH, "-s", serial, "shell", "pm", "list", "packages", "-3"])
    if rc != 0:
        return []
    return [line.replace("package:", "").strip() for line in out.splitlines() if line.strip()]


async def launch_app(serial: str, package_name: str) -> bool:
    """Launch an app by package name using monkey."""
    rc, out, _ = await _run(
        [ADB_PATH, "-s", serial, "shell", "monkey", "-p", package_name,
         "-c", "android.intent.category.LAUNCHER", "1"],
        timeout=15,
    )
    return rc == 0


async def force_stop_app(serial: str, package_name: str) -> None:
    """Force-stop an app."""
    await _run([ADB_PATH, "-s", serial, "shell", "am", "force-stop", package_name])


async def take_screenshot_adb(serial: str, local_path: str) -> bool:
    """Take a screenshot via ADB and pull it locally."""
    remote = "/sdcard/screen.png"
    rc1, _, _ = await _run([ADB_PATH, "-s", serial, "shell", "screencap", "-p", remote])
    if rc1 != 0:
        return False
    rc2, _, _ = await _run([ADB_PATH, "-s", serial, "pull", remote, local_path])
    return rc2 == 0


# ── Emulator management ──────────────────────────────────────────

async def list_avds() -> list[str]:
    """List available AVDs."""
    rc, out, _ = await _run([EMULATOR_PATH, "-list-avds"])
    if rc != 0:
        return []
    return [line.strip() for line in out.splitlines() if line.strip()]


async def start_emulator(avd_name: str, port: int = 5554) -> Optional[str]:
    """Start an emulator in the background. Returns expected serial."""
    serial = f"emulator-{port}"
    logger.info("Starting emulator %s on port %d", avd_name, port)
    # Start in background – don't await completion
    proc = await asyncio.create_subprocess_exec(
        EMULATOR_PATH, "-avd", avd_name,
        "-port", str(port),
        "-no-snapshot-save",
        "-no-audio",
        "-gpu", "swiftshader_indirect",
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    # Give it a moment to start binding
    await asyncio.sleep(5)
    return serial


async def get_screen_resolution(serial: str) -> tuple[int, int]:
    """Get device screen resolution."""
    rc, out, _ = await _run([ADB_PATH, "-s", serial, "shell", "wm", "size"])
    if rc == 0:
        match = re.search(r"(\d+)x(\d+)", out)
        if match:
            return int(match.group(1)), int(match.group(2))
    return 1080, 1920  # default
