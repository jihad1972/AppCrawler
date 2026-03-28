"""AI Vision provider – Gemini-based screen analysis for mobile app crawling."""

import base64
import json
import logging
import re
from pathlib import Path
from typing import Optional

import google.generativeai as genai

from config import GEMINI_API_KEY, GEMINI_MODEL
from models import ActionDecision, ActionType

logger = logging.getLogger(__name__)

# ── System prompt ────────────────────────────────────────────────

SYSTEM_PROMPT = """You are an AI agent that explores Android mobile applications by analyzing screenshots.
Your goal is to methodically explore as many UNIQUE screens and features of the app as possible.

RULES:
1. You receive a screenshot of the current screen.
2. You must decide the NEXT action to take.
3. Prefer unexplored UI elements – buttons, tabs, menu items, list items, icons.
4. Avoid repeating the same action. If you've tapped something before, try something else.
5. Use BACK to return from dead-ends or detail screens.
6. Use SWIPE_UP to scroll down and reveal more content.
7. Do NOT interact with system UI (status bar, navigation bar) unless necessary.
8. If you see a login/signup screen, try to skip or dismiss it.
9. If you encounter a dialog/popup, dismiss it first.

PREVIOUSLY VISITED SCREENS (summaries):
{visited_screens}

PREVIOUS ACTIONS (last 5):
{recent_actions}

Respond ONLY with valid JSON in this exact format:
{{
  "action": "tap|swipe_up|swipe_down|swipe_left|swipe_right|back|type_text|home|wait",
  "x": <int or null>,
  "y": <int or null>,
  "text": "<string or null>",
  "reasoning": "<brief explanation of why this action>",
  "element_description": "<what UI element you are interacting with>",
  "screen_label": "<short label for this screen, e.g. 'Settings Page', 'Home Tab'>"
}}
"""


def _configure_gemini():
    """Configure the Gemini API."""
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY environment variable is not set")
    genai.configure(api_key=GEMINI_API_KEY)


def _load_image_as_part(image_path: str) -> dict:
    """Load an image file and return it as a Gemini content part."""
    path = Path(image_path)
    data = path.read_bytes()
    mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
    return {"mime_type": mime, "data": data}


def _parse_response(text: str) -> Optional[ActionDecision]:
    """Parse the AI response JSON into an ActionDecision."""
    # Extract JSON from response (may be wrapped in ```json blocks)
    json_match = re.search(r'\{[^{}]*\}', text, re.DOTALL)
    if not json_match:
        logger.error("No JSON found in AI response: %s", text[:200])
        return None

    try:
        data = json.loads(json_match.group())
    except json.JSONDecodeError as e:
        logger.error("JSON parse error: %s in %s", e, text[:200])
        return None

    action_str = data.get("action", "wait").lower()
    try:
        action_type = ActionType(action_str)
    except ValueError:
        logger.warning("Unknown action '%s', defaulting to wait", action_str)
        action_type = ActionType.WAIT

    return ActionDecision(
        action=action_type,
        x=data.get("x"),
        y=data.get("y"),
        text=data.get("text"),
        reasoning=data.get("reasoning", ""),
        element_description=data.get("element_description", ""),
    ), data.get("screen_label", "Unknown Screen")


async def analyze_screen(
    screenshot_path: str,
    visited_screens: list[str],
    recent_actions: list[str],
) -> tuple[Optional[ActionDecision], str]:
    """
    Analyze a screenshot and return the next action to take.
    Returns (ActionDecision, screen_label).
    """
    _configure_gemini()

    model = genai.GenerativeModel(GEMINI_MODEL)

    visited_str = "\n".join(f"- {s}" for s in visited_screens[-15:]) if visited_screens else "None yet"
    actions_str = "\n".join(f"- {a}" for a in recent_actions[-5:]) if recent_actions else "None yet"

    prompt = SYSTEM_PROMPT.format(
        visited_screens=visited_str,
        recent_actions=actions_str,
    )

    image_part = _load_image_as_part(screenshot_path)

    try:
        response = model.generate_content(
            [prompt, image_part],
            generation_config=genai.GenerationConfig(
                temperature=0.4,
                max_output_tokens=500,
            ),
        )
        result = _parse_response(response.text)
        if result is None:
            return None, "Unknown"
        action, screen_label = result
        logger.info("AI decision: %s at (%s,%s) – %s", action.action, action.x, action.y, action.reasoning)
        return action, screen_label

    except Exception as e:
        logger.error("Gemini API error: %s", e)
        return None, "Error"
