"""
models.py
Pydantic request/response models for the Hypatia Sims4ModGuard API.
"""

from typing import Any, Optional
from pydantic import BaseModel, Field


# ── /analyze-log ─────────────────────────────────────────────────────────────

class AnalyzeLogRequest(BaseModel):
    content: str = Field(..., description="Raw text content of lastException.txt")
    patch_version: str = Field("1.121", description="Current Sims 4 patch version string")


class ModError(BaseModel):
    type: str = Field(..., description="Error type, e.g. 'script_error', 'conflict', 'missing_dependency'")
    mod_name: str = Field(..., description="Name of the offending mod")
    action: str = Field(..., description="Recommended action, e.g. 'update', 'remove', 'disable'")
    update_url: Optional[str] = Field(None, description="URL to get the latest version")


class AnalyzeLogResponse(BaseModel):
    summary: str = Field(..., description="Plain-language summary of what went wrong")
    errors: list[ModError] = Field(default_factory=list)
    severity: str = Field(..., description="Overall severity: critical | warning | info")
    fix_steps: list[str] = Field(default_factory=list, description="Ordered list of fix instructions")


# ── /check-mod ───────────────────────────────────────────────────────────────

class CheckModRequest(BaseModel):
    filename: str = Field(..., description="Package filename, e.g. 'SomeMod_v2.package'")


class CheckModResponse(BaseModel):
    known_conflict: bool
    details: Optional[dict[str, Any]] = None
    suggestion: str


# ── /submit-conflict ─────────────────────────────────────────────────────────

class SubmitConflictRequest(BaseModel):
    mod_name: str = Field(..., description="Human-readable mod name")
    file_pattern: str = Field(..., description="Filename pattern or substring to match")
    broken_since_patch: str = Field(..., description="Patch version where conflict started")
    notes: str = Field("", description="Additional notes or reproduction steps")
    submitter: str = Field("anonymous", description="Discord handle or username of submitter")


class SubmitConflictResponse(BaseModel):
    issue_url: str


# ── /health ──────────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    version: str
    conflicts_loaded: int
