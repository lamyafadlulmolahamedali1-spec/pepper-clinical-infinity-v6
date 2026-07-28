"""
╔════════════════════════════════════════════════════════════════════╗
║  PEPPER CLINICAL V6 — Children Router                            ║
╚════════════════════════════════════════════════════════════════════╝
"""
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db, User, Child
from app.core.security import encrypt_field, decrypt_field
from app.api.deps import get_current_user
from app.models.schemas import ChildCreate, ChildOut

router = APIRouter(prefix="/api/children", tags=["Children"])


def _to_out(c: Child) -> ChildOut:
    return ChildOut(
        id=c.id,
        name=decrypt_field(c.name_enc),
        age=c.age,
        diagnosis=decrypt_field(c.diagnosis_enc),
        skill_motor=c.skill_motor,
        skill_cognitive=c.skill_cognitive,
        skill_verbal=c.skill_verbal,
        skill_math=c.skill_math,
        skill_social=c.skill_social,
        total_sessions=c.total_sessions,
        total_score=c.total_score,
    )


@router.get("", response_model=List[ChildOut])
def list_children(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    children = db.query(Child).filter(Child.parent_id == user.id).all()
    return [_to_out(c) for c in children]


@router.post("", response_model=ChildOut, status_code=status.HTTP_201_CREATED)
def create_child(body: ChildCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    child = Child(
        parent_id=user.id,
        name_enc=encrypt_field(body.name),
        age=body.age,
        diagnosis_enc=encrypt_field(body.diagnosis),
    )
    db.add(child)
    db.commit()
    db.refresh(child)
    return _to_out(child)


@router.get("/{child_id}", response_model=ChildOut)
def get_child(child_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    child = db.query(Child).filter(Child.id == child_id, Child.parent_id == user.id).first()
    if not child:
        raise HTTPException(status_code=404, detail="Child not found")
    return _to_out(child)


@router.delete("/{child_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_child(child_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    child = db.query(Child).filter(Child.id == child_id, Child.parent_id == user.id).first()
    if not child:
        raise HTTPException(status_code=404, detail="Child not found")
    db.delete(child)
    db.commit()
