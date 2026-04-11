from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound, VideoUnavailable
from typing import Optional


class YouTubeTranscriptService:
    """
    Servicio para obtener transcripciones de YouTube sin descargar el video completo.
    Útil para clasificar videos antes de procesarlos.
    """

    def get_transcript(self, video_id: str, language: str = 'es') -> Optional[str]:
        """
        Obtiene la transcripción de un video de YouTube.

        Args:
            video_id: ID del video de YouTube
            language: Código de idioma (default: 'es' para español)

        Returns:
            Texto de la transcripción o None si no está disponible
        """
        try:
            # Intentar obtener transcripción en español
            ytt_api = YouTubeTranscriptApi()
            transcript_list = ytt_api.fetch(
                video_id,
                languages=[language, 'es-ES', 'es-MX', 'es-419']  # Diferentes variantes de español
            )

            # Concatenar todo el texto
            full_text = ' '.join([snippet.text for snippet in transcript_list])
            return full_text

        except (TranscriptsDisabled, NoTranscriptFound, VideoUnavailable) as e:
            # No hay transcripción disponible
            return None
        except Exception as e:
            # Cualquier otro error
            print(f"Error obteniendo transcripción para {video_id}: {str(e)}")
            return None

    def get_transcript_sample(self, video_id: str, max_chars: int = 3000) -> Optional[str]:
        """
        Obtiene una muestra de la transcripción (primeros N caracteres).
        Útil para clasificación rápida sin procesar todo el texto.

        Args:
            video_id: ID del video de YouTube
            max_chars: Número máximo de caracteres a retornar

        Returns:
            Muestra del texto o None si no está disponible
        """
        full_transcript = self.get_transcript(video_id)

        if not full_transcript:
            return None

        # Retornar solo los primeros max_chars caracteres
        return full_transcript[:max_chars]


# Singleton instance
youtube_transcript_service = YouTubeTranscriptService()
