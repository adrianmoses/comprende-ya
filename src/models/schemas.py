from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, HttpUrl


class VideoRequest(BaseModel):
    url: HttpUrl


class Question(BaseModel):
    question: str
    answers: List[str]
    correct_answer: int  # indice de la respuesta correcta
    explanation: Optional[str] = None


class TimestampedQuestion(BaseModel):
    """Pregunta asociada a un momento del video"""

    timestamp: float  # Segundos desde el inicio
    question: str
    answers: List[str]
    correct_answer: int
    explanation: Optional[str] = None


class FillInBlankExercise(BaseModel):
    """Ejercicio de completar espacios en blanco"""

    id: Optional[int] = None
    original_text: str
    exercise_text: str  # Texto con "___" para los blanks
    answers: Dict[str, str]  # {"blank_0": "palabra_correcta", ...}
    hints: Dict[str, str]  # {"blank_0": "verbo - subjuntivo", ...}
    start_time: float
    end_time: float
    difficulty: str  # "facil", "medio", "dificil"


class VideoResponse(BaseModel):
    video_id: str
    title: str
    duration: int
    transcript: str
    questions: List[TimestampedQuestion]  # Ahora con timestamps
    fill_in_blank_exercises: Optional[List[FillInBlankExercise]] = None


class TranscriptSegment(BaseModel):
    """Segmentos de transcripción ocn timestamp"""

    text: str
    start: float
    end: float


class DetailedTranscript(BaseModel):
    """Transcripción completa con segmentos"""

    full_text: str
    segments: List[TranscriptSegment]
    duration: float


class AutopsyGrammarRow(BaseModel):
    tag: str
    text: str


class AutopsyExplainRequest(BaseModel):
    phrase: str = Field(min_length=1, max_length=200)
    start_time: float = Field(ge=0)


class AutopsyEntryResponse(BaseModel):
    id: int
    video_id: str  # YouTube id, no la PK de la tabla videos
    phrase: str
    start_time: float
    register: str
    grammar: List[AutopsyGrammarRow]
    natural_notes: List[str]
    created_at: datetime


class ChunkSaveRequest(BaseModel):
    video_id: str  # YouTube id
    phrase: str = Field(min_length=1, max_length=200)
    start_time: float = Field(ge=0)


class ChunkResponse(BaseModel):
    id: int
    video_id: str  # YouTube id
    source_title: str  # título del vídeo, para Mis frases
    phrase: str
    start_time: float
    prompts: List[str]
    created_at: datetime
