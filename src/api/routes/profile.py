"""Endpoints del perfil del usuario + KPIs de Inicio (022).

Un único perfil (sin auth). `GET` devuelve identidad + los tres KPIs vivos en
una sola llamada; `POST /session` recibe latidos de escucha desde Escuchando;
`PUT` edita nombre/nivel (lo usará el panel de Ajustes, 023)."""

from fastapi import APIRouter, Depends, Response
from sqlmodel import Session

from db import get_session
from models.schemas import ProfileResponse, ProfileUpdateRequest, SessionRequest
from repositories.profile_repository import ProfileRepository

router = APIRouter(prefix="/api/profile", tags=["profile"])


def _build_response(repo: ProfileRepository) -> ProfileResponse:
    profile = repo.get_or_create_profile()
    streak = repo.streak()
    correct, total = repo.comprehension()
    comprehension = round(correct / total * 100) if total else None
    return ProfileResponse(
        name=profile.name,
        level=profile.level,
        dia=streak,
        week_minutes=repo.week_minutes(),
        streak=streak,
        comprehension=comprehension,
    )


@router.get("", response_model=ProfileResponse)
def get_profile(db: Session = Depends(get_session)):
    """Identidad + KPIs (esta semana, racha, comprensión) en una sola llamada."""
    return _build_response(ProfileRepository(db))


@router.post("/session", status_code=204)
def add_session(body: SessionRequest, db: Session = Depends(get_session)):
    """Registra un tramo de escucha. El frontend acumula segundos de
    reproducción y los va vaciando aquí."""
    ProfileRepository(db).add_session(body.seconds)
    return Response(status_code=204)


@router.put("", response_model=ProfileResponse)
def update_profile(body: ProfileUpdateRequest, db: Session = Depends(get_session)):
    """Edita nombre/nivel del perfil y devuelve el perfil + KPIs actualizados."""
    repo = ProfileRepository(db)
    repo.update_profile(name=body.name, level=body.level)
    return _build_response(repo)
