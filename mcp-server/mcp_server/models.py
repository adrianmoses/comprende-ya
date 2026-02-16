"""Pydantic models for MCP tool I/O."""

from __future__ import annotations

from pydantic import BaseModel


class TopicSummary(BaseModel):
    id: str
    name: str
    level: str
    category: str
    description: str = ""
    vocabulary: list[dict] = []
    grammar_rules: list[dict] = []
    phrases: list[dict] = []


class LearnerProfile(BaseModel):
    learner_id: str
    name: str
    mastered: list[str] = []
    struggling: list[str] = []
    due_for_review: list[str] = []
    unseen: list[str] = []


class AttemptResult(BaseModel):
    learner_id: str
    topic_id: str
    result: str  # "correct" or "incorrect"
    new_interval_days: float
    new_ease_factor: float
    next_review: str


class SessionContext(BaseModel):
    session_id: str
    learner_summary: str
    topic_content: list[TopicSummary] = []
    suggested_prompt_additions: str = ""
