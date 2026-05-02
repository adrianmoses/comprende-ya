from datetime import datetime
from typing import List, Optional

from sqlmodel import Session, select

from models.database import ProcessingJob


class ProcessingJobRepository:
    """Repository para el estado persistido de los flows de procesamiento."""

    VALID_STATUSES = ("PENDING", "RUNNING", "COMPLETED", "FAILED")

    def __init__(self, session: Session):
        self.session = session

    def create_pending(
        self,
        flow_run_id: str,
        youtube_url: str,
        youtube_video_id: str,
    ) -> ProcessingJob:
        job = ProcessingJob(
            flow_run_id=flow_run_id,
            youtube_url=youtube_url,
            youtube_video_id=youtube_video_id,
            status="PENDING",
        )
        self.session.add(job)
        self.session.commit()
        self.session.refresh(job)
        return job

    def get_by_flow_run_id(self, flow_run_id: str) -> Optional[ProcessingJob]:
        statement = select(ProcessingJob).where(
            ProcessingJob.flow_run_id == flow_run_id
        )
        return self.session.exec(statement).first()

    def list(self, skip: int = 0, limit: int = 50) -> List[ProcessingJob]:
        statement = (
            select(ProcessingJob)
            .order_by(ProcessingJob.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(self.session.exec(statement).all())

    def mark_running(self, flow_run_id: str) -> Optional[ProcessingJob]:
        return self._set_status(flow_run_id, "RUNNING")

    def mark_completed(
        self, flow_run_id: str, video_id: Optional[int] = None
    ) -> Optional[ProcessingJob]:
        return self._set_status(flow_run_id, "COMPLETED", video_id=video_id)

    def mark_failed(self, flow_run_id: str, error: str) -> Optional[ProcessingJob]:
        return self._set_status(flow_run_id, "FAILED", error=error)

    def _set_status(
        self,
        flow_run_id: str,
        status: str,
        *,
        error: Optional[str] = None,
        video_id: Optional[int] = None,
    ) -> Optional[ProcessingJob]:
        job = self.get_by_flow_run_id(flow_run_id)
        if job is None:
            return None
        job.status = status
        job.updated_at = datetime.utcnow()
        if error is not None:
            job.error = error
        if video_id is not None:
            job.video_id = video_id
        self.session.add(job)
        self.session.commit()
        self.session.refresh(job)
        return job
