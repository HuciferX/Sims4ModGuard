"""
api_client.py
Client for connecting the Windows app to the Hypatia AI backend service.
Falls back gracefully if the server is unavailable.
"""

import json
from typing import Optional
from urllib.request import urlopen, Request
from urllib.error import URLError

DEFAULT_SERVER = "https://api.hySims.app"
TIMEOUT = 10


def is_available(server: str = DEFAULT_SERVER) -> bool:
    """Check if the Hypatia backend is reachable."""
    try:
        req = Request(f"{server}/health", headers={"User-Agent": "Sims4ModGuard/1.0"})
        with urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
            return data.get("status") == "ok"
    except Exception:
        return False


def analyze_log(log_content: str, patch_version: str = "1.121",
                server: str = DEFAULT_SERVER) -> Optional[dict]:
    """
    Send lastException.txt content to Hypatia AI for analysis.

    Returns structured analysis:
    {
        "summary": "Plain English summary",
        "errors": [{"type", "mod_name", "action", "update_url"}],
        "severity": "critical|warning|info",
        "fix_steps": ["Step 1...", "Step 2..."]
    }
    Returns None if server unavailable.
    """
    try:
        payload = json.dumps({
            "content": log_content[:50000],  # cap at 50KB
            "patch_version": patch_version
        }).encode("utf-8")

        req = Request(
            f"{server}/analyze-log",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "Sims4ModGuard/1.0"
            },
            method="POST"
        )
        with urlopen(req, timeout=TIMEOUT) as resp:
            return json.loads(resp.read())
    except Exception:
        return None


def check_mod(filename: str, server: str = DEFAULT_SERVER) -> Optional[dict]:
    """
    Check if a specific mod filename is in the Hypatia conflict database.

    Returns:
    {
        "known_conflict": true/false,
        "details": {...conflict entry...},
        "suggestion": "Plain English suggestion"
    }
    Returns None if server unavailable.
    """
    try:
        payload = json.dumps({"filename": filename}).encode("utf-8")
        req = Request(
            f"{server}/check-mod",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "Sims4ModGuard/1.0"
            },
            method="POST"
        )
        with urlopen(req, timeout=TIMEOUT) as resp:
            return json.loads(resp.read())
    except Exception:
        return None


def get_conflicts(server: str = DEFAULT_SERVER) -> Optional[list]:
    """
    Fetch the full conflicts database from Hypatia.
    Returns list of conflict entries, or None if unavailable.
    """
    try:
        req = Request(f"{server}/conflicts",
                      headers={"User-Agent": "Sims4ModGuard/1.0"})
        with urlopen(req, timeout=TIMEOUT) as resp:
            data = json.loads(resp.read())
            return data.get("conflicts", [])
    except Exception:
        return None


def submit_conflict(mod_name: str, file_pattern: str, broken_since: str,
                    notes: str, submitter: str = "community",
                    server: str = DEFAULT_SERVER) -> Optional[dict]:
    """
    Submit a new conflict to the community database.
    Returns {"issue_url": "..."} on success, None on failure.
    """
    try:
        payload = json.dumps({
            "mod_name": mod_name,
            "file_pattern": file_pattern,
            "broken_since_patch": broken_since,
            "notes": notes,
            "submitter": submitter
        }).encode("utf-8")
        req = Request(
            f"{server}/submit-conflict",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "Sims4ModGuard/1.0"
            },
            method="POST"
        )
        with urlopen(req, timeout=TIMEOUT) as resp:
            return json.loads(resp.read())
    except Exception:
        return None
