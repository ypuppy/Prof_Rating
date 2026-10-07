from typing import Optional

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from db import get_db
from models import ProfessorCreate, ReviewCreate
from tables import Professor, Review

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def professor_to_dict(p: Professor, avg_rating=None, review_count: int = 0) -> dict:
    """Build the API response explicitly so DB-internal columns don't leak."""
    return {
        "id": p.id,
        "name": p.name,
        "department": p.department,
        "faculty": p.faculty,
        "avg_rating": round(float(avg_rating), 2) if avg_rating is not None else None,
        "review_count": review_count,
    }


def review_to_dict(r: Review) -> dict:
    return {
        "id": r.id,
        "professor_id": r.professor_id,
        "rating": r.rating,
        "module_code": r.module_code,
        "comment": r.comment,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


def professors_with_stats():
    """SELECT professors + their average rating and review count (LEFT JOIN keeps profs with no reviews)."""
    return (
        select(
            Professor,
            func.avg(Review.rating).label("avg_rating"),
            func.count(Review.id).label("review_count"),
        )
        .outerjoin(Review, Review.professor_id == Professor.id)
        .group_by(Professor.id)
    )


@app.get("/health")
def health():
    return {"ok": True, "service": "backend"}


@app.post("/professors")
def create_professor(payload: ProfessorCreate, db: Session = Depends(get_db)):
    prof = Professor(
        name=payload.name.strip(),
        department=payload.department.strip() if payload.department else None,
        faculty=payload.faculty.strip() if payload.faculty else None,
    )
    db.add(prof)
    try:
        db.commit()
    except IntegrityError:
        # uq_professors_name_lower rejected it — no race between "check" and "insert"
        db.rollback()
        raise HTTPException(status_code=409, detail="Professor already exists")

    return professor_to_dict(prof)


@app.get("/professors")
def list_professors(query: Optional[str] = None, limit: int = 50, db: Session = Depends(get_db)):
    """
    List professors. Supports basic name search via ?query=...
    limit is capped to avoid returning too many rows in one request.
    """
    safe_limit = max(1, min(limit, 200))

    stmt = professors_with_stats().order_by(Professor.name).limit(safe_limit)
    if query and query.strip():
        # autoescape so % and _ in the query are matched literally
        stmt = stmt.where(Professor.name.icontains(query.strip(), autoescape=True))

    items = [professor_to_dict(p, avg, count) for p, avg, count in db.execute(stmt)]
    return {"items": items, "count": len(items)}


@app.get("/professors/{professor_id}")
def get_professor(professor_id: int, db: Session = Depends(get_db)):
    row = db.execute(professors_with_stats().where(Professor.id == professor_id)).first()
    if not row:
        raise HTTPException(status_code=404, detail="Professor not found")

    p, avg, count = row
    return professor_to_dict(p, avg, count)


@app.post("/professors/{professor_id}/reviews")
def create_review(professor_id: int, payload: ReviewCreate, db: Session = Depends(get_db)):
    if db.get(Professor, professor_id) is None:
        raise HTTPException(status_code=404, detail="Professor not found")

    review = Review(
        professor_id=professor_id,
        rating=payload.rating,
        module_code=payload.module_code.strip().upper() if payload.module_code else None,
        comment=payload.comment.strip() if payload.comment else None,
    )
    db.add(review)
    db.commit()
    db.refresh(review)  # load server-generated created_at

    return review_to_dict(review)


@app.get("/professors/{professor_id}/reviews")
def list_reviews(professor_id: int, limit: int = 50, skip: int = 0, db: Session = Depends(get_db)):
    safe_limit = max(1, min(limit, 200))
    safe_skip = max(0, skip)

    stmt = (
        select(Review)
        .where(Review.professor_id == professor_id)
        .order_by(Review.created_at.desc())
        .offset(safe_skip)
        .limit(safe_limit)
    )
    items = [review_to_dict(r) for r in db.scalars(stmt)]
    return {"items": items, "count": len(items)}
