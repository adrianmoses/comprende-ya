from pydantic import BaseModel, HttpUrl
from typing import Optional, List, Dict

class VideoRequest(BaseModel):
    url: HttpUrl


class Question(BaseModel):
    question: str
    answers: List[str]
    correct_answer: int # indice de la respuesta correcta
    explanation: Optional[str] = None

class TimestampedQuestion(BaseModel):
    """Pregunta asociada a un momento del video"""
    timestamp: float # Segundos desde el inicio
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
    questions: List[TimestampedQuestion] # Ahora con timestamps
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


