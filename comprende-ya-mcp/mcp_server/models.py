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


class EvidenceEvent(BaseModel):
    concept_id: str
    signal: str  # produced_correctly, produced_with_errors, recognized, etc.
    outcome: float  # 0.0-1.0
    session_id: str | None = None
    context_id: str | None = None
    activity_type: str | None = None
    timestamp: str | None = None  # ISO 8601; server fills if omitted


class StudiesState(BaseModel):
    concept_id: str
    mastery: float = 0.0
    projected_mastery: float = 0.0  # mastery after decay projection to now
    confidence: float = 0.0
    half_life_days: float = 1.0
    practice_count: int = 0
    last_evidence_at: str | None = None
    last_outcome: float | None = None
    trend: str = "plateau"
    first_seen_at: str | None = None


class ConfusionPair(BaseModel):
    concept_a: str
    concept_b: str
    evidence_count: int = 0
    last_seen_at: str | None = None


class EffectiveContext(BaseModel):
    context_id: str
    effectiveness: float = 0.0
    sample_count: int = 0


class LearnerProfile(BaseModel):
    learner_id: str
    mastered: list[str] = []
    progressing: list[str] = []
    decaying: list[str] = []
    unseen: list[str] = []
    confusion_pairs: list[ConfusionPair] = []
    total_evidence_count: int = 0


class InteractionTurn(BaseModel):
    role: str  # "learner" or "teacher"
    text: str
    timestamp: str | None = None
    turn_index: int = 0


class AssessmentResult(BaseModel):
    session_id: str
    learner_id: str
    turns_assessed: int
    evidence_events_created: int
    concepts_assessed: list[str] = []
    context_id: str | None = None
    studies_updated: list[dict] = []
    confusions_detected: list[dict] = []
    judge_model: str = ""
    errors: list[str] = []
