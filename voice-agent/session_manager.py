"""Session lifecycle manager for structured and free conversation modes.

Pure Python class — no web framework dependency.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

import mcp_client

logger = logging.getLogger(__name__)

BASE_PERSONA = (
    "Eres un profesor de español para un estudiante de nivel B2. "
    "Habla de forma natural, corrige errores con amabilidad y adapta el nivel. "
    "Responde con frases cortas y claras."
)


@dataclass
class TurnRecord:
    role: str  # "learner" or "teacher"
    text: str
    timestamp: str
    turn_index: int = 0


@dataclass
class SessionState:
    session_id: str
    learner_id: str
    mode: Literal["structured", "free"]
    plan: dict | None = None
    current_activity_index: int = 0
    activity_start_time: datetime | None = None
    turn_buffer: list[TurnRecord] = field(default_factory=list)
    turn_counter: int = 0
    _assessment_lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class SessionManager:
    """Manages session lifecycle, prompt generation, and activity transitions."""

    def __init__(self, learner_id: str) -> None:
        self.learner_id = learner_id
        self.state: SessionState | None = None

    async def start_structured_session(self, duration_min: float = 30.0) -> dict:
        """Start a structured session with a curriculum plan."""
        plan = await mcp_client.plan_session(self.learner_id, duration_min)
        if not plan or not plan.get("activities"):
            # Fall back to free mode if planning fails
            return self.start_free_session()

        session_id = plan.get("session_id", str(uuid.uuid4()))
        self.state = SessionState(
            session_id=session_id,
            learner_id=self.learner_id,
            mode="structured",
            plan=plan,
            current_activity_index=0,
            activity_start_time=datetime.now(timezone.utc),
        )
        return plan

    def start_free_session(self) -> dict:
        """Start a free conversation session (no plan)."""
        session_id = str(uuid.uuid4())
        self.state = SessionState(
            session_id=session_id,
            learner_id=self.learner_id,
            mode="free",
        )
        return {
            "session_id": session_id,
            "mode": "free",
            "learner_id": self.learner_id,
        }

    def get_system_prompt(self) -> str:
        """Build system prompt: base persona + current activity instructions."""
        if not self.state or self.state.mode == "free":
            return BASE_PERSONA

        plan = self.state.plan
        if not plan:
            return BASE_PERSONA

        activities = plan.get("activities", [])
        idx = self.state.current_activity_index
        if idx >= len(activities):
            return BASE_PERSONA

        activity = activities[idx]
        instructions = activity.get("instructions", "")
        concept_names = activity.get("concept_names", [])
        activity_type = activity.get("activity_type", "")

        prompt = BASE_PERSONA
        prompt += f"\n\nActividad actual ({activity_type}): {instructions}"
        if concept_names:
            prompt += f"\nConceptos objetivo: {', '.join(concept_names)}"
        return prompt

    def record_turn(self, role: str, text: str) -> None:
        """Append a turn to the buffer."""
        if not self.state:
            return
        ts = datetime.now(timezone.utc).isoformat()
        self.state.turn_counter += 1
        self.state.turn_buffer.append(
            TurnRecord(
                role=role,
                text=text,
                timestamp=ts,
                turn_index=self.state.turn_counter,
            )
        )

    def should_check_activity(self) -> bool:
        """True if elapsed time >= activity's duration_estimate_min."""
        if not self.state or self.state.mode == "free":
            return False
        if not self.state.plan or not self.state.activity_start_time:
            return False

        activities = self.state.plan.get("activities", [])
        idx = self.state.current_activity_index
        if idx >= len(activities):
            return False

        duration = activities[idx].get("duration_estimate_min", 5.0)
        elapsed = (
            datetime.now(timezone.utc) - self.state.activity_start_time
        ).total_seconds() / 60.0
        return elapsed >= duration

    async def check_and_transition(self) -> dict | None:
        """Fire assessment (background), replan, transition activity.

        Returns activity_change dict or None if no transition.
        """
        if not self.state or self.state.mode == "free":
            return None
        if not self.state.plan:
            return None

        activities = self.state.plan.get("activities", [])
        idx = self.state.current_activity_index

        if idx >= len(activities):
            return None

        current_activity = activities[idx]

        # Fire assessment as background task for buffered turns
        turns_to_assess = [
            {
                "role": t.role,
                "text": t.text,
                "timestamp": t.timestamp,
                "turn_index": t.turn_index,
            }
            for t in self.state.turn_buffer
        ]

        target_concept_ids = current_activity.get("concept_ids", [])

        if turns_to_assess:
            asyncio.create_task(
                self._fire_assessment(
                    turns_to_assess, target_concept_ids, self.state.session_id
                )
            )

        # Clear buffer for next activity
        self.state.turn_buffer = []

        # Compute elapsed time for replan
        elapsed_min = 0.0
        if self.state.activity_start_time:
            elapsed_min = (
                datetime.now(timezone.utc) - self.state.activity_start_time
            ).total_seconds() / 60.0

        # Call replan
        progress = {
            "activity_index": idx,
            "outcome_so_far": 0.5,  # default; real outcome comes from assessment
            "time_elapsed_min": elapsed_min,
        }
        replan_result = await mcp_client.replan_activity(
            self.learner_id, self.state.plan, progress
        )

        action = replan_result.get("action", "continue")
        updated_activities = replan_result.get("updated_activities")

        if updated_activities is not None:
            self.state.plan["activities"] = updated_activities

        # Advance to next activity
        next_idx = idx if action == "scaffold" else idx + 1
        activities = self.state.plan.get("activities", [])

        if next_idx >= len(activities):
            # Session complete
            return {
                "type": "session_end",
                "session_id": self.state.session_id,
                "reason": "all_activities_completed",
            }

        self.state.current_activity_index = next_idx
        self.state.activity_start_time = datetime.now(timezone.utc)

        next_activity = activities[next_idx]
        return {
            "type": "activity_change",
            "activity_index": next_idx,
            "activity": next_activity,
            "replan_action": action,
            "replan_reason": replan_result.get("reason", ""),
            "remaining_activities": len(activities) - next_idx,
        }

    async def end_session(self) -> dict:
        """End session: fire final assessment for remaining turns, return summary."""
        if not self.state:
            return {"error": "no_active_session"}

        # Assess remaining turns
        if self.state.turn_buffer and self.state.plan:
            activities = self.state.plan.get("activities", [])
            idx = self.state.current_activity_index
            target_ids = (
                activities[idx].get("concept_ids", []) if idx < len(activities) else []
            )
            turns = [
                {
                    "role": t.role,
                    "text": t.text,
                    "timestamp": t.timestamp,
                    "turn_index": t.turn_index,
                }
                for t in self.state.turn_buffer
            ]
            if turns:
                asyncio.create_task(
                    self._fire_assessment(turns, target_ids, self.state.session_id)
                )

        summary: dict[str, Any] = {
            "session_id": self.state.session_id,
            "mode": self.state.mode,
            "total_turns": self.state.turn_counter,
        }

        if self.state.plan:
            summary["activities_completed"] = self.state.current_activity_index
            summary["total_activities"] = len(self.state.plan.get("activities", []))

        self.state = None
        return summary

    async def _fire_assessment(
        self,
        turns: list[dict],
        target_concept_ids: list[str],
        session_id: str,
    ) -> None:
        """Background task: assess turns via MCP."""
        try:
            await mcp_client.assess_interaction(
                learner_id=self.learner_id,
                session_id=session_id,
                turns=turns,
                target_concept_ids=target_concept_ids or None,
            )
        except Exception as e:
            logger.warning("Background assessment failed: %s", e)

    def get_session_info(self) -> dict | None:
        """Return current session state for REST queries."""
        if not self.state:
            return None

        info: dict[str, Any] = {
            "session_id": self.state.session_id,
            "mode": self.state.mode,
            "turn_count": self.state.turn_counter,
        }

        if self.state.plan:
            activities = self.state.plan.get("activities", [])
            info["current_activity_index"] = self.state.current_activity_index
            info["total_activities"] = len(activities)
            if self.state.current_activity_index < len(activities):
                info["current_activity"] = activities[self.state.current_activity_index]
            if self.state.activity_start_time:
                elapsed = (
                    datetime.now(timezone.utc) - self.state.activity_start_time
                ).total_seconds() / 60.0
                info["activity_elapsed_min"] = round(elapsed, 1)

        return info
