"""
The logged-in user's own reviews.

Reviews can't be edited. To change one, the user deletes it; the deleted copy is cached
in `deleted_reviews` for DELETED_REVIEW_TTL so the frontend can offer to rewrite it,
pre-filled. Submitting the rewrite (POST /professors/{id}/reviews with
replaces_deleted_review_id) creates a new review and clears the cached copy.

  GET    /me/reviews                  -> my reviews, newest first, with professor info
  DELETE /me/reviews/{id}             -> delete one of mine, returns the cached copy
  GET    /me/deleted-reviews          -> cached copies that haven't expired
  DELETE /me/deleted-reviews/{id}     -> discard a cached copy now
"""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import Session, joinedload

from auth import get_current_user
from db import get_db
from tables import DeletedReview, Professor, Review, User

DELETED_REVIEW_TTL = timedelta(hours=24)

router = APIRouter(prefix="/me", tags=["me"])


def now() -> datetime:
    return datetime.now(timezone.utc)


def professor_summary(p: Professor) -> dict:
    return {"id": p.id, "name": p.name, "department": p.department, "faculty": p.faculty}


def my_review_to_dict(r: Review) -> dict:
    return {
        "id": r.id,
        "professor": professor_summary(r.professor),
        "rating": r.rating,
        "module_code": r.module_code,
        "comment": r.comment,
        "academic_year": r.academic_year,
        "semester": r.semester,
        "created_at": r.created_at.isoformat(),
    }


def deleted_review_to_dict(d: DeletedReview) -> dict:
    return {
        "id": d.id,
        "professor": professor_summary(d.professor),
        "rating": d.rating,
        "module_code": d.module_code,
        "comment": d.comment,
        "academic_year": d.academic_year,
        "semester": d.semester,
        "original_created_at": d.original_created_at.isoformat(),
        "deleted_at": d.deleted_at.isoformat(),
        "expires_at": d.expires_at.isoformat(),
    }


def purge_expired(db: Session) -> None:
    """Hard-delete cached reviews past their expiry. Cheap thanks to the expires_at index."""
    db.execute(delete(DeletedReview).where(DeletedReview.expires_at <= now()))


@router.get("/reviews")
def list_my_reviews(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    reviews = db.scalars(
        select(Review)
        .options(joinedload(Review.professor))
        .where(Review.user_id == user.id)
        .order_by(Review.created_at.desc())
    ).all()
    items = [my_review_to_dict(r) for r in reviews]
    return {"items": items, "count": len(items)}


@router.delete("/reviews/{review_id}")
def delete_my_review(review_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    review = db.scalars(
        select(Review)
        .options(joinedload(Review.professor))
        .where(Review.id == review_id, Review.user_id == user.id)
    ).first()
    if review is None:
        # Same answer for "doesn't exist" and "not yours", so ids can't be probed
        raise HTTPException(status_code=404, detail="Review not found")

    purge_expired(db)
    cached = DeletedReview(
        user_id=user.id,
        professor_id=review.professor_id,
        rating=review.rating,
        module_code=review.module_code,
        comment=review.comment,
        academic_year=review.academic_year,
        semester=review.semester,
        original_created_at=review.created_at,
        expires_at=now() + DELETED_REVIEW_TTL,
    )
    db.add(cached)
    db.delete(review)
    db.commit()  # move happens in one transaction: never both, never neither
    db.refresh(cached)

    return deleted_review_to_dict(cached)


@router.get("/deleted-reviews")
def list_my_deleted_reviews(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    purge_expired(db)
    db.commit()
    cached = db.scalars(
        select(DeletedReview)
        .options(joinedload(DeletedReview.professor))
        .where(DeletedReview.user_id == user.id)
        .order_by(DeletedReview.deleted_at.desc())
    ).all()
    items = [deleted_review_to_dict(d) for d in cached]
    return {"items": items, "count": len(items)}


@router.delete("/deleted-reviews/{deleted_id}")
def discard_deleted_review(deleted_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    result = db.execute(
        delete(DeletedReview).where(DeletedReview.id == deleted_id, DeletedReview.user_id == user.id)
    )
    db.commit()
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Deleted review not found")
    return {"ok": True}


def take_deleted_review(db: Session, user: User, deleted_id: int, professor_id: int) -> None:
    """
    Used when submitting a rewrite: removes the cached copy in the caller's transaction.
    Raises if it isn't this user's, has expired, or belongs to another professor.
    """
    cached = db.scalars(
        select(DeletedReview)
        .where(
            DeletedReview.id == deleted_id,
            DeletedReview.user_id == user.id,
            DeletedReview.expires_at > now(),
        )
        .with_for_update()
    ).first()
    if cached is None:
        raise HTTPException(status_code=404, detail="That deleted review is no longer available")
    if cached.professor_id != professor_id:
        raise HTTPException(status_code=400, detail="That deleted review is for a different professor")
    db.delete(cached)
