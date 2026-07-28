"""
╔════════════════════════════════════════════════════════════════════╗
║  PEPPER CLINICAL V6 — Sessions Router (start · end · tasks · stats)║
╚════════════════════════════════════════════════════════════════════╝
"""
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db, User, Child, TherapySession
from app.api.deps import get_current_user
from app.models.schemas import (
    SessionStart, SessionEnd, SessionOut, TaskRequest,
)
from app.services.task_generator import TaskGenerator

router = APIRouter(prefix="/api/sessions", tags=["Sessions"])


def _own_child(db: Session, user: User, child_id: str) -> Child:
    child = db.query(Child).filter(Child.id == child_id, Child.parent_id == user.id).first()
    if not child:
        raise HTTPException(status_code=404, detail="Child not found")
    return child


@router.post("/start", response_model=SessionOut, status_code=status.HTTP_201_CREATED)
def start_session(body: SessionStart, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _own_child(db, user, body.child_id)
    sess = TherapySession(
        user_id=user.id,
        child_id=body.child_id,
        protocol=body.protocol,
        started_at=datetime.now(timezone.utc),
    )
    db.add(sess)
    db.commit()
    db.refresh(sess)
    return SessionOut(
        id=sess.id, started_at=sess.started_at, ended_at=sess.ended_at,
        duration_sec=sess.duration_sec, score=sess.score, tasks_total=sess.tasks_total,
        tasks_success=sess.tasks_success, tasks_mastered=sess.tasks_mastered,
        avg_attention=sess.avg_attention, protocol=sess.protocol,
    )


@router.post("/tasks/generate")
def generate_tasks(body: TaskRequest, user: User = Depends(get_current_user)):
    tasks = TaskGenerator.generate(domain=body.domain, level=body.level, count=body.count)
    return {"count": len(tasks), "tasks": tasks}


@router.post("/end", response_model=SessionOut)
def end_session(body: SessionEnd, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    sess = db.query(TherapySession).filter(
        TherapySession.id == body.session_id, TherapySession.user_id == user.id
    ).first()
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")
    if sess.ended_at is not None:
        raise HTTPException(status_code=409, detail="Session already ended")

    sess.ended_at = datetime.now(timezone.utc)
    sess.duration_sec = body.duration_sec
    sess.score = body.score
    sess.tasks_total = body.tasks_total
    sess.tasks_success = body.tasks_success
    sess.tasks_fail = body.tasks_fail
    sess.tasks_mastered = body.tasks_mastered
    sess.avg_attention = body.avg_attention
    sess.dominant_emotion = body.dominant_emotion

    # Update child stats + adaptive skill bump
    child = db.query(Child).filter(Child.id == sess.child_id).first()
    if child:
        child.total_sessions += 1
        child.total_score += body.score
        # Adaptive: success ratio nudges skills
        if body.tasks_total > 0:
            ratio = body.tasks_success / body.tasks_total
            bump = (ratio - 0.5) * 4  # -2..+2
            for attr in ("skill_motor", "skill_cognitive", "skill_verbal", "skill_math", "skill_social"):
                cur = getattr(child, attr)
                setattr(child, attr, max(0.0, min(100.0, cur + bump)))

    db.commit()
    db.refresh(sess)
    return SessionOut(
        id=sess.id, started_at=sess.started_at, ended_at=sess.ended_at,
        duration_sec=sess.duration_sec, score=sess.score, tasks_total=sess.tasks_total,
        tasks_success=sess.tasks_success, tasks_mastered=sess.tasks_mastered,
        avg_attention=sess.avg_attention, protocol=sess.protocol,
    )


@router.get("/history/{child_id}", response_model=List[SessionOut])
def session_history(child_id: str, limit: int = 20,
                    user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _own_child(db, user, child_id)
    sessions = (db.query(TherapySession)
                .filter(TherapySession.child_id == child_id,
                        TherapySession.ended_at.isnot(None))
                .order_by(TherapySession.started_at.desc())
                .limit(min(limit, 100)).all())
    return [SessionOut(
        id=s.id, started_at=s.started_at, ended_at=s.ended_at,
        duration_sec=s.duration_sec, score=s.score, tasks_total=s.tasks_total,
        tasks_success=s.tasks_success, tasks_mastered=s.tasks_mastered,
        avg_attention=s.avg_attention, protocol=s.protocol,
    ) for s in sessions]


@router.get("/stats/{child_id}")
def child_stats(child_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    child = _own_child(db, user, child_id)
    sessions = (db.query(TherapySession)
                .filter(TherapySession.child_id == child_id,
                        TherapySession.ended_at.isnot(None)).all())
    total_mastered = sum(s.tasks_mastered for s in sessions)
    avg_attn = (sum(s.avg_attention for s in sessions) / len(sessions)) if sessions else 0
    return {
        "total_sessions": child.total_sessions,
        "total_score": child.total_score,
        "total_mastered": total_mastered,
        "avg_attention": round(avg_attn, 1),
        "skills": {
            "motor": child.skill_motor, "cognitive": child.skill_cognitive,
            "verbal": child.skill_verbal, "math": child.skill_math,
            "social": child.skill_social,
        },
    }
