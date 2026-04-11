import anthropic
import json
from typing import Optional, Dict
from config import settings


class DialectClassifierService:
    """
    Servicio para clasificar dialectos de español usando Claude.
    Puede trabajar con transcripciones de videos ya procesados o muestras de YouTube.
    """

    def __init__(self):
        self.client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    def classify_dialect(self, transcription: str) -> Optional[Dict]:
        """
        Clasifica el dialecto de español de una transcripción.

        Args:
            transcription: Texto transcrito en español

        Returns:
            Dict con dialect, confidence, y signals, o None si hay error
        """
        if not transcription or len(transcription.strip()) < 50:
            # Transcripción muy corta para clasificar
            return None

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

        try:
            message = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}]
            )

            response_text = message.content[0].text
            result = json.loads(response_text)

            return result

        except Exception as e:
            print(f"Error clasificando dialecto: {str(e)}")
            return None

    def classify_from_sample(self, transcription_sample: str) -> Optional[Dict]:
        """
        Clasifica usando una muestra de transcripción (más rápido).
        Añade una nota indicando que es basado en una muestra.

        Args:
            transcription_sample: Muestra del texto transcrito

        Returns:
            Dict con clasificación o None si hay error
        """
        result = self.classify_dialect(transcription_sample)

        if result:
            # Añadir nota de que es basado en muestra
            result['is_sample'] = True

        return result


# Singleton instance
dialect_classifier = DialectClassifierService()
