"""Custom Pipecat frame serializer for the comprende-ya webapp protocol.

Bridges the webapp's raw PCM int16 + JSON text protocol with Pipecat's frame system:
- Incoming binary → InputAudioRawFrame
- Incoming text   → ignored (no client JSON messages used yet)
- Outgoing OutputAudioRawFrame → raw audio bytes
- Outgoing OutputTransportMessageFrame → JSON string
"""

from __future__ import annotations

import json
import logging

from pipecat.frames.frames import (
    Frame,
    InputAudioRawFrame,
    OutputAudioRawFrame,
    OutputTransportMessageFrame,
)
from pipecat.serializers.base_serializer import FrameSerializer

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16000
NUM_CHANNELS = 1


class ComprendeSerializer(FrameSerializer):
    """Serializes/deserializes frames for the comprende-ya webapp WebSocket protocol."""

    async def serialize(self, frame: Frame) -> str | bytes | None:
        if isinstance(frame, OutputAudioRawFrame):
            logger.debug("serialize: audio out %d bytes", len(frame.audio))
            return frame.audio
        if isinstance(frame, OutputTransportMessageFrame):
            logger.info("serialize: message out %s", type(frame.message))
            return json.dumps(frame.message)
        return None

    async def deserialize(self, data: str | bytes) -> Frame | None:
        if isinstance(data, bytes):
            logger.debug("deserialize: audio in %d bytes", len(data))
            return InputAudioRawFrame(
                audio=data,
                sample_rate=SAMPLE_RATE,
                num_channels=NUM_CHANNELS,
            )
        logger.debug("deserialize: text frame ignored: %s", data[:100] if data else "")
        return None
