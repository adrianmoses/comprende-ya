from fastapi import HTTPException
from sqlmodel import Session, select
from typing import Optional, List
import json
from models.database import Video, Question as DBQuestion
from models.schemas import VideoResponse, TimestampedQuestion
import anthropic
import os


class ClassifierRepository:

    def __init__(self, session: Session):
        self.session = session
        self.client = anthropic.Anthropic(
            api_key=os.environ.get("ANTHROPIC_API_KEY")
        )

    def classify_dialect(self, transcription: str) -> dict:
        prompt = f"""Analiza este texto transcrito y clasifica el dialecto de español.

    Texto:
    {transcription}

    Clasifica como: España (Peninsular), México, Argentina, Caribe, Andino, u Otro.

    Proporciona:
    1. Clasificación
    2. Nivel de confianza (0-100%)
    3. Top 3 señales lingüísticas que usaste (vocabulario específico, formas verbales, expresiones)

    Responde ÚNICAMENTE con JSON (sin markdown):
    {{
      "dialect": "...",
      "confidence": 85,
      "signals": ["usa 'tío' repetidamente", "vosotros en vez de ustedes", "ceceo implícito en texto"]
    }}
    """

        message = self.client.messages.create(
            model="claude-sonnet-4-20250514",  # o "claude-sonnet-4-20241022"
            max_tokens=1024,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        # Claude devuelve el contenido en message.content[0].text
        response_text = message.content[0].text

        # Parsear el JSON
        import json
        result = json.loads(response_text)

        return result

    # Uso:

    def classify_video(self, video: Video) -> dict:
        if not video:
            return {}

        transcription = video.full_transcript_data
        if not transcription:
            return {}

        return self.classify_dialect(transcription)


