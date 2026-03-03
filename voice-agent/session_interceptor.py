"""Pipecat FrameProcessors that integrate SessionManager into the pipeline.

Two processors work together:

- TranscriptionObserver: placed before the user aggregator to capture
  transcription text and record learner turns in SessionManager.
- SessionInterceptor: placed after TTS to capture LLM response frames,
  emit metrics JSON, and handle activity transitions.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from pipecat.frames.frames import (
    Frame,
    LLMFullResponseEndFrame,
    OutputTransportMessageFrame,
    TTSStartedFrame,
    TTSStoppedFrame,
    TTSTextFrame,
    TranscriptionFrame,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

if TYPE_CHECKING:
    from pipecat.processors.aggregators.llm_context import LLMContext

    from session_manager import SessionManager

logger = logging.getLogger(__name__)


class TranscriptionObserver(FrameProcessor):
    """Observes TranscriptionFrames before the user aggregator consumes them.

    Records the learner turn in SessionManager and timestamps for metrics.
    Must be placed in the pipeline between STT and the user aggregator.
    """

    def __init__(self, interceptor: SessionInterceptor, **kwargs) -> None:
        super().__init__(name="TranscriptionObserver", **kwargs)
        self._interceptor = interceptor

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        await super().process_frame(frame, direction)

        if (
            isinstance(frame, TranscriptionFrame)
            and direction == FrameDirection.DOWNSTREAM
        ):
            text = frame.text.strip()
            if text:
                self._interceptor.record_user_turn(text)

        await self.push_frame(frame, direction)


class SessionInterceptor(FrameProcessor):
    """Intercepts LLM/TTS frames after TTS to emit metrics and manage sessions.

    Must be placed in the pipeline after the TTS service.
    """

    def __init__(
        self,
        session_manager: SessionManager,
        context: LLMContext,
        **kwargs,
    ) -> None:
        super().__init__(name="SessionInterceptor", **kwargs)
        self._sm = session_manager
        self._context = context

        # Per-turn state — accumulated across all TTS sentences in one LLM turn
        self._last_user_text: str = ""
        self._response_buffer: str = ""
        self._turn_start_time: float = 0.0
        self._llm_end_time: float = 0.0
        self._llm_done: bool = False
        self._tts_active: bool = False

    def record_user_turn(self, text: str) -> None:
        """Called by TranscriptionObserver when a transcription arrives."""
        self._last_user_text = text
        self._turn_start_time = time.monotonic()
        self._llm_done = False
        self._sm.record_turn("learner", text)
        logger.info("Learner: %s", text[:80])

        # Refresh system prompt (may change after activity transition)
        self._update_system_prompt()

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        await super().process_frame(frame, direction)

        if isinstance(frame, TTSStartedFrame):
            self._tts_active = True
        elif isinstance(frame, TTSTextFrame) and direction == FrameDirection.DOWNSTREAM:
            self._response_buffer += frame.text
        elif isinstance(frame, LLMFullResponseEndFrame):
            self._llm_end_time = time.monotonic()
            self._llm_done = True
            response = self._response_buffer.strip()
            if response:
                self._sm.record_turn("teacher", response)
                logger.info("Teacher: %s", response[:80])
        elif isinstance(frame, TTSStoppedFrame):
            self._tts_active = False
            # Emit metrics only after the last TTS sentence of the turn
            if self._llm_done:
                await self._on_turn_complete()

        # Always push the frame through (we observe, don't filter)
        await self.push_frame(frame, direction)

    async def _on_turn_complete(self) -> None:
        """Full turn complete (LLM done + final TTS sentence finished). Emit metrics."""
        now = time.monotonic()

        if self._turn_start_time > 0 and self._last_user_text:
            llm_ms = (
                (self._llm_end_time - self._turn_start_time) * 1000
                if self._llm_end_time > self._turn_start_time
                else 0
            )
            tts_ms = (now - self._llm_end_time) * 1000 if self._llm_end_time > 0 else 0
            total_ms = (now - self._turn_start_time) * 1000

            metrics_msg = {
                "type": "metrics",
                "data": {
                    "stt_ms": 0,  # STT timing not available in pipeline mode
                    "llm_ms": round(llm_ms, 2),
                    "tts_ms": round(tts_ms, 2),
                    "total_ms": round(total_ms, 2),
                },
                "transcription": self._last_user_text,
                "response": self._response_buffer.strip(),
            }
            await self.push_frame(
                OutputTransportMessageFrame(message=metrics_msg),
                FrameDirection.DOWNSTREAM,
            )
            logger.info("Metrics: total=%.0fms", total_ms)

        # Check for activity transition (structured mode)
        if self._sm.should_check_activity():
            logger.info("Activity duration elapsed — checking transition")
            transition = await self._sm.check_and_transition()
            if transition:
                await self.push_frame(
                    OutputTransportMessageFrame(message=transition),
                    FrameDirection.DOWNSTREAM,
                )
                logger.info("Sent transition: %s", transition.get("type"))
                self._update_system_prompt()

        # Reset per-turn state
        self._last_user_text = ""
        self._response_buffer = ""
        self._turn_start_time = 0.0
        self._llm_end_time = 0.0
        self._llm_done = False

    def _update_system_prompt(self) -> None:
        """Update the LLM context's system message from session manager."""
        new_prompt = self._sm.get_system_prompt()
        messages = self._context.messages
        if messages and messages[0].get("role") == "system":
            messages[0]["content"] = new_prompt
        else:
            messages.insert(0, {"role": "system", "content": new_prompt})
