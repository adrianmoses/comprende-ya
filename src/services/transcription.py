from openai import OpenAI
from config import settings
from models.schemas import DetailedTranscript, TranscriptSegment


class TranscriptionService:

    def __init__(self) -> None:
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)

    def transcribe(self, audio_path: str) -> str:
        """
        Transcribe audio usando Whisper
        :param audio_path:
        :return:
        """

        with open(audio_path, "rb") as audio_file:
            transcript = self.client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                language="es",
            )

        return transcript.text

    def transcribe_with_timestamps(self, audio_path: str) -> DetailedTranscript:
        """
        Transcripción con timestamps por segmento
        :param audio_path:
        :return:
        """

        with open(audio_path, "rb") as audio_file:
            transcript = self.client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                language="es",
                response_format="verbose_json",
                timestamp_granularities=["segment"] # Segmentos (frames)
            )

        # Extraer segmentos
        segments = [
            TranscriptSegment(
                text=seg.text,
                start=seg.start,
                end=seg.end
            )
            for seg in transcript.segments
        ]

        return DetailedTranscript(
            full_text=transcript.text,
            segments=segments,
            duration=transcript.duration,
        )



transcription_service = TranscriptionService()