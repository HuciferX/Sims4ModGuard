"""
analyzer.py
Claude-powered log analysis for Sims 4 mod conflicts.

Uses claude-haiku-4-5 for fast, cost-effective analysis.
System prompt is cached with cache_control for repeated requests.
Falls back gracefully when no ANTHROPIC_API_KEY is configured.
"""

import json
import logging
import os
import re
from typing import Optional

import anthropic

from models import AnalyzeLogResponse, ModError

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

MODEL = "claude-haiku-4-5"
MAX_TOKENS = 4096

HYPATIA_SYSTEM_PROMPT = """You are 🦉 Hypatia, an expert AI assistant specializing in Sims 4 mod compatibility, conflict diagnosis, and crash recovery. You have deep knowledge of:

- The Sims 4 scripting engine, DBPF package format, and tuning system
- Common script mods (MCCC, WickedWhims, Basemental, UI Cheats Extension, Wonderful Whims, etc.)
- CC (Custom Content) conflicts and resource key collisions
- lastException.txt and exception log format and how to interpret stack traces
- Patch history and which mods break on which EA game updates
- Where to find official/latest mod downloads (Patreon, itch.io, Tumblr, ModTheSims, CurseForge)

When analyzing a lastException.txt log:
1. Identify EXACTLY which mod files are responsible (be specific: exact .package or .ts4script filenames when visible)
2. Classify the error type: script_error, resource_conflict, missing_dependency, outdated_mod, corrupted_file, or game_bug
3. Assign an overall severity: critical (game crash/won't load), warning (broken feature), info (minor glitch)
4. Give clear, numbered fix steps that any player can follow
5. Always include the official update URL when you know the mod

IMPORTANT: You MUST respond with ONLY valid JSON in exactly this structure — no markdown fences, no preamble:
{
  "summary": "One to two sentence plain English explanation of what happened",
  "errors": [
    {
      "type": "script_error|resource_conflict|missing_dependency|outdated_mod|corrupted_file|game_bug",
      "mod_name": "Exact mod name or filename",
      "action": "update|remove|disable|reinstall|verify_game_files",
      "update_url": "https://... or null"
    }
  ],
  "severity": "critical|warning|info",
  "fix_steps": [
    "Step 1: ...",
    "Step 2: ..."
  ]
}"""

# ── Fallback analysis (no API key) ────────────────────────────────────────────

def _fallback_analysis(log_content: str, patch_version: str) -> AnalyzeLogResponse:
    """
    Very lightweight heuristic analysis used when no ANTHROPIC_API_KEY is set.
    Searches for known patterns in the log to produce a basic response.
    """
    lower = log_content.lower()
    errors: list[ModError] = []
    fix_steps: list[str] = []
    severity = "info"

    # Look for common script mod references in exception logs
    script_mod_patterns = [
        ("wickedwhims", "WickedWhims", "https://turbodriver.itch.io/wickedwhims"),
        ("mc_cmd_center", "MC Command Center", "https://deaderpoolmc.tumblr.com/"),
        ("basemental", "Basemental Drugs/Gambling", "https://basementalcc.com/"),
        ("ui_cheats", "UI Cheats Extension", "https://www.patreon.com/weerbesu"),
        ("wonderful_whims", "Wonderful Whims", "https://turbodriver.itch.io/wonderfulwhims"),
        ("lumpinou", "Lumpinou's Pregnancy Mod", "https://lumpinou.itch.io/"),
        ("lot51", "Lot51 Core Library", "https://lot51.cc/"),
    ]

    for pattern, display_name, url in script_mod_patterns:
        if pattern in lower:
            errors.append(ModError(
                type="script_error",
                mod_name=display_name,
                action="update",
                update_url=url,
            ))
            fix_steps.append(f"Update {display_name} to the latest version from {url}")

    # Detect severity clues
    if any(k in lower for k in ["attributeerror", "typeerror", "exception", "traceback"]):
        severity = "critical" if not errors else "warning"
    elif errors:
        severity = "warning"

    if not errors:
        fix_steps = [
            "Move ALL mods out of your Mods folder to a backup location.",
            "Run the game to confirm it loads cleanly without mods.",
            "Add mods back in batches of 10-20 using the 50/50 method to isolate the culprit.",
            "Check https://sims4updates.net/ for the latest patch compatibility notes.",
        ]

    return AnalyzeLogResponse(
        summary=(
            f"Basic heuristic analysis for patch {patch_version} — "
            "set ANTHROPIC_API_KEY for full AI-powered diagnosis. "
            + (f"Detected {len(errors)} likely culprit(s)." if errors else "No obvious culprits auto-detected; manual 50/50 testing recommended.")
        ),
        errors=errors,
        severity=severity,
        fix_steps=fix_steps or ["No API key configured. Set ANTHROPIC_API_KEY for detailed fix steps."],
    )


# ── Claude analysis ───────────────────────────────────────────────────────────

def _parse_claude_response(text: str) -> dict:
    """
    Extract JSON from Claude's response.
    Handles responses with or without markdown fences.
    """
    # Strip markdown code fences if present
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text.strip())

    # Try to extract just the JSON object if there's surrounding text
    json_match = re.search(r"\{.*\}", text, re.DOTALL)
    if json_match:
        text = json_match.group()

    return json.loads(text)


async def analyze_log(log_content: str, patch_version: str) -> AnalyzeLogResponse:
    """
    Analyze a Sims 4 lastException.txt log using Claude.
    Falls back to heuristic analysis if ANTHROPIC_API_KEY is not set.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        logger.warning("ANTHROPIC_API_KEY not set — using heuristic fallback analysis.")
        return _fallback_analysis(log_content, patch_version)

    client = anthropic.AsyncAnthropic(api_key=api_key)

    # Truncate very large logs to avoid token waste (keep first + last sections)
    max_log_chars = 12_000
    if len(log_content) > max_log_chars:
        half = max_log_chars // 2
        log_content = (
            log_content[:half]
            + f"\n\n[... {len(log_content) - max_log_chars} characters truncated ...]\n\n"
            + log_content[-half:]
        )

    user_message = (
        f"Analyze this Sims 4 lastException.txt log from patch version {patch_version}.\n\n"
        f"```\n{log_content}\n```\n\n"
        "Return ONLY the JSON structure described in your instructions. No extra text."
    )

    try:
        response = await client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=[
                {
                    "type": "text",
                    "text": HYPATIA_SYSTEM_PROMPT,
                    # Cache the large system prompt — saves tokens on every repeated request
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[
                {"role": "user", "content": user_message}
            ],
        )

        raw_text = response.content[0].text
        logger.debug(
            "Claude usage — input: %d, output: %d, cache_read: %d, cache_write: %d",
            response.usage.input_tokens,
            response.usage.output_tokens,
            getattr(response.usage, "cache_read_input_tokens", 0),
            getattr(response.usage, "cache_creation_input_tokens", 0),
        )

        data = _parse_claude_response(raw_text)

        errors = [
            ModError(
                type=e.get("type", "script_error"),
                mod_name=e.get("mod_name", "Unknown Mod"),
                action=e.get("action", "update"),
                update_url=e.get("update_url"),
            )
            for e in data.get("errors", [])
        ]

        return AnalyzeLogResponse(
            summary=data.get("summary", "Analysis complete."),
            errors=errors,
            severity=data.get("severity", "warning"),
            fix_steps=data.get("fix_steps", []),
        )

    except json.JSONDecodeError as exc:
        logger.error("Failed to parse Claude JSON response: %s", exc)
        # Return partial fallback with raw summary
        return AnalyzeLogResponse(
            summary="Hypatia analyzed the log but encountered a formatting issue. See fix_steps for raw guidance.",
            errors=[],
            severity="warning",
            fix_steps=[
                "AI response could not be parsed as structured JSON.",
                "Try removing recently added mods one at a time.",
                "Check https://sims4updates.net/ for your patch version compatibility notes.",
            ],
        )
    except anthropic.APIError as exc:
        logger.error("Anthropic API error: %s", exc)
        raise
