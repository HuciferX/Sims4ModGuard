"""
main.py
Hypatia Sims4ModGuard — FastAPI backend service.

Endpoints:
  POST /analyze-log      — AI-powered lastException.txt analysis
  POST /check-mod        — Check a mod filename against the conflicts database
  GET  /conflicts        — Return full known conflicts database
  POST /submit-conflict  — Submit a new conflict as a GitHub issue
  GET  /health           — Service health check

Run locally:
  uvicorn main:app --host 0.0.0.0 --port 8765 --reload

Or with Docker:
  docker build -t hypatia-sims4-service .
  docker run -p 8765:8765 --env-file .env hypatia-sims4-service
"""

import logging
import os
from contextlib import asynccontextmanager

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

import analyzer
import conflict_db
from models import (
    AnalyzeLogRequest,
    AnalyzeLogResponse,
    CheckModRequest,
    CheckModResponse,
    HealthResponse,
    SubmitConflictRequest,
    SubmitConflictResponse,
)

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger(__name__)

SERVICE_VERSION = "1.0.0"
GITHUB_REPO = "HuciferX/Sims4ModGuard"
GITHUB_API_BASE = "https://api.github.com"


# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load conflict DB at startup."""
    logger.info("🦉 Hypatia Sims4ModGuard service starting up …")
    await conflict_db.load_db()
    logger.info("Conflict DB loaded: %d entries.", conflict_db.db_size())
    yield
    logger.info("🦉 Hypatia service shutting down.")


# ── App setup ─────────────────────────────────────────────────────────────────

app = FastAPI(
    title="🦉 Hypatia Sims4ModGuard API",
    description=(
        "AI-powered Sims 4 mod conflict analysis and fix service. "
        "Built by Hucifer & 🦉 Hypatia — free for the community forever. "
        "GitHub: https://github.com/HuciferX/Sims4ModGuard"
    ),
    version=SERVICE_VERSION,
    lifespan=lifespan,
)

# Allow the Windows GUI and any web frontend to call this service
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse, tags=["system"])
async def health():
    """
    Service health check.
    Returns status, version, and number of conflict DB entries loaded.
    """
    return HealthResponse(
        status="ok",
        version=SERVICE_VERSION,
        conflicts_loaded=conflict_db.db_size(),
    )


@app.post("/analyze-log", response_model=AnalyzeLogResponse, tags=["analysis"])
async def analyze_log(request: AnalyzeLogRequest):
    """
    Analyze a Sims 4 lastException.txt log using 🦉 Hypatia (Claude AI).

    Send the raw text content of your lastException.txt file and the current
    game patch version. Returns a structured breakdown of mods causing issues,
    severity rating, and step-by-step fix instructions.

    Falls back to heuristic analysis if no ANTHROPIC_API_KEY is configured.
    """
    if not request.content.strip():
        raise HTTPException(status_code=400, detail="Log content must not be empty.")

    try:
        result = await analyzer.analyze_log(
            log_content=request.content,
            patch_version=request.patch_version,
        )
        return result
    except Exception as exc:
        logger.exception("Error during log analysis: %s", exc)
        raise HTTPException(status_code=500, detail=f"Analysis failed: {exc}") from exc


@app.post("/check-mod", response_model=CheckModResponse, tags=["conflicts"])
async def check_mod(request: CheckModRequest):
    """
    Check a single mod filename against the known conflicts database.

    Pass any .package or .ts4script filename. Hypatia will match it against
    the curated registry and return conflict details and a recommendation.
    """
    filename = request.filename.strip()
    if not filename:
        raise HTTPException(status_code=400, detail="filename must not be empty.")

    entry = conflict_db.lookup_mod(filename)

    if entry is None:
        return CheckModResponse(
            known_conflict=False,
            details=None,
            suggestion=(
                "This mod is not in Hypatia's conflict registry. "
                "It may still conflict with other mods — use the /analyze-log endpoint "
                "with your lastException.txt for a full diagnosis."
            ),
        )

    known_conflicts = entry.get("known_conflicts", [])
    conflict_note = ""
    if known_conflicts:
        conflict_note = f" Known to conflict with: {', '.join(known_conflicts)}."

    patreon_note = ""
    if entry.get("patreon_required"):
        patreon_note = " Note: the latest compatible version requires a Patreon subscription."

    suggestion = (
        f"Update '{entry['display_name']}' by {entry['author']} from {entry['update_url']}."
        + conflict_note
        + patreon_note
        + f" {entry.get('free_note', '')}"
    ).strip()

    return CheckModResponse(
        known_conflict=True,
        details={
            "id": entry["id"],
            "display_name": entry["display_name"],
            "author": entry["author"],
            "update_url": entry["update_url"],
            "patreon_required": entry.get("patreon_required", False),
            "ww_dependency": entry.get("ww_dependency", False),
            "description": entry.get("description", ""),
            "known_conflicts": known_conflicts,
            "broken_since_patch": entry.get("broken_since_patch"),
        },
        suggestion=suggestion,
    )


@app.get("/conflicts", tags=["conflicts"])
async def get_conflicts():
    """
    Return the full known conflicts database.

    The database is loaded from the embedded baseline at startup and extended
    with any community entries from the GitHub repo's data/conflicts.json file.
    """
    return {
        "count": conflict_db.db_size(),
        "conflicts": conflict_db.get_db(),
    }


@app.post("/submit-conflict", response_model=SubmitConflictResponse, tags=["community"])
async def submit_conflict(request: SubmitConflictRequest):
    """
    Submit a newly discovered mod conflict as a GitHub issue.

    Community submissions are reviewed and added to the conflicts database.
    Requires GITHUB_TOKEN env var with repo issue-creation permission.
    """
    github_token = os.getenv("GITHUB_TOKEN", "")

    issue_title = f"[Conflict Report] {request.mod_name} — broken since {request.broken_since_patch}"
    issue_body = (
        f"## 🦉 Hypatia Community Conflict Report\n\n"
        f"**Mod Name:** {request.mod_name}\n"
        f"**File Pattern:** `{request.file_pattern}`\n"
        f"**Broken Since Patch:** {request.broken_since_patch}\n"
        f"**Submitted By:** {request.submitter}\n\n"
        f"### Notes\n{request.notes or '_No additional notes provided._'}\n\n"
        f"---\n"
        f"*Submitted via Hypatia Sims4ModGuard API — free community tool by Hucifer & 🦉 Hypatia*"
    )

    if not github_token:
        # No token — return a placeholder URL with instructions
        logger.warning("GITHUB_TOKEN not set; cannot create GitHub issue.")
        raise HTTPException(
            status_code=503,
            detail=(
                "GITHUB_TOKEN is not configured on this server. "
                "Please open an issue manually at "
                f"https://github.com/{GITHUB_REPO}/issues/new with title: {issue_title!r}"
            ),
        )

    headers = {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    payload = {
        "title": issue_title,
        "body": issue_body,
        "labels": ["conflict-report", "community-submission"],
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            f"{GITHUB_API_BASE}/repos/{GITHUB_REPO}/issues",
            headers=headers,
            json=payload,
        )

    if resp.status_code not in (200, 201):
        logger.error("GitHub API error %s: %s", resp.status_code, resp.text)
        raise HTTPException(
            status_code=502,
            detail=f"GitHub API returned {resp.status_code}: {resp.json().get('message', resp.text)}",
        )

    issue_url = resp.json().get("html_url", "")
    logger.info("Conflict submitted as GitHub issue: %s", issue_url)
    return SubmitConflictResponse(issue_url=issue_url)
