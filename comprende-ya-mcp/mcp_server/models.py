"""Pydantic models for MCP tool I/O."""

from __future__ import annotations

from pydantic import BaseModel


class ConceptSummary(BaseModel):
    id: str
    name: str
    description: str = ""
    cefr_level: str = ""
    category: str = ""
    decay_rate: str = ""
    typical_difficulty: float = 0.0
    mastery_signals: list[str] = []
    tags: list[str] = []
    prerequisites: list[str] = []
    related: list[str] = []
    contrasts_with: list[str] = []


class LearnerProfile(BaseModel):
    learner_id: str
    name: str
    mastered: list[str] = []
    struggling: list[str] = []
    due_for_review: list[str] = []
    unseen: list[str] = []


class AttemptResult(BaseModel):
    learner_id: str
    concept_id: str
    result: str  # "correct" or "incorrect"
    new_interval_days: float
    new_ease_factor: float
    next_review: str


class SessionContext(BaseModel):
    session_id: str
    learner_summary: str
    concept_content: list[ConceptSummary] = []
    suggested_prompt_additions: str = ""
