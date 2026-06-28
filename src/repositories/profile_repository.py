"""Repositorio del perfil singleton + agregados de KPIs de Inicio (022).

Sin auth: hay un único perfil (id=1) creado de forma perezosa. Los KPIs se
calculan sobre datos que ya almacenamos (`AnswerProgress`) más el registro de
escucha (`StudySession`). Fronteras de día/semana en UTC, semana desde el lunes.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional, Tuple

from sqlalchemy import func
from sqlmodel import Session, select

from models.database import AnswerProgress, Profile, StudySession


def _week_start_utc(now: Optional[datetime] = None) -> datetime:
    """Medianoche UTC del lunes de la semana actual."""
    today = (now or datetime.utcnow()).date()
    monday = today - timedelta(days=today.weekday())
    return datetime(monday.year, monday.month, monday.day)


class ProfileRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_or_create_profile(self) -> Profile:
        """Devuelve el perfil singleton, creándolo con los valores por defecto
        en el primer acceso. Robusto frente al TRUNCATE de los tests y a una BD
        recién migrada (no sembramos la fila en la migración)."""
        profile = self.session.get(Profile, 1)
        if profile is None:
            profile = Profile()
            self.session.add(profile)
            self.session.commit()
            self.session.refresh(profile)
        return profile

    def update_profile(self, name: Optional[str] = None, level: Optional[str] = None) -> Profile:
        profile = self.get_or_create_profile()
        if name is not None:
            profile.name = name
        if level is not None:
            profile.level = level
        self.session.add(profile)
        self.session.commit()
        self.session.refresh(profile)
        return profile

    def add_session(self, seconds: int) -> StudySession:
        row = StudySession(seconds=seconds)
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return row

    def week_minutes(self) -> int:
        """Minutos enteros de escucha en la semana actual (lunes→, UTC)."""
        total_seconds = self.session.exec(
            select(func.coalesce(func.sum(StudySession.seconds), 0)).where(
                StudySession.created_at >= _week_start_utc()
            )
        ).one()
        return int(total_seconds) // 60

    def comprehension(self) -> Tuple[int, int]:
        """`(correctas, total)` de MCQs respondidas, histórico completo. El
        llamador renderiza `None` cuando total == 0 (no `0 %`)."""
        total = self.session.exec(select(func.count()).select_from(AnswerProgress)).one()
        correct = self.session.exec(
            select(func.count()).select_from(AnswerProgress).where(AnswerProgress.is_correct)
        ).one()
        return int(correct), int(total)

    def streak(self) -> int:
        """Días consecutivos de actividad de estudio. Un día está «activo» si
        tiene una `StudySession` o un `AnswerProgress` (OQ3). La racha es
        «vigente» si hay actividad hoy o ayer (gracia para «el día aún no acabó»),
        y se cuenta hacia atrás hasta el primer día inactivo. Sin actividad → 0."""
        session_days = self.session.exec(select(StudySession.created_at)).all()
        answer_days = self.session.exec(select(AnswerProgress.answered_at)).all()
        active = {d.date() for d in session_days} | {d.date() for d in answer_days}
        if not active:
            return 0

        today = datetime.utcnow().date()
        if today in active:
            cursor = today
        elif (today - timedelta(days=1)) in active:
            cursor = today - timedelta(days=1)
        else:
            return 0

        count = 0
        while cursor in active:
            count += 1
            cursor -= timedelta(days=1)
        return count
