from typing import Optional

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import case, func, literal, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from auth import get_current_user
from auth import router as auth_router
from db import get_db
from me import router as me_router
from me import take_deleted_review
from reference import router as reference_router
from models import ProfessorCreate, ReviewCreate
from names import name_words, normalize_name
from tables import Module, Professor, Review, User

app = FastAPI()
app.include_router(auth_router)
app.include_router(me_router)
app.include_router(reference_router)

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
        "academic_year": r.academic_year,
        "semester": r.semester,
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


def modules_taught(db: Session, professor_id: int) -> list[dict]:
    """Module codes students mentioned in this professor's reviews, most-reviewed first."""
    stmt = (
        select(Review.module_code, Module.title, func.count().label("review_count"))
        .outerjoin(Module, Module.code == Review.module_code)  # title is unknown for codes not on NUSMods
        .where(Review.professor_id == professor_id, Review.module_code.is_not(None))
        .group_by(Review.module_code, Module.title)
        .order_by(func.count().desc(), Review.module_code)
    )
    return [
        {"code": code, "title": title, "review_count": n}
        for code, title, n in db.execute(stmt)
    ]


@app.get("/health")
def health():
    return {"ok": True, "service": "backend"}


# pg_trgm similarity at or above this counts as "maybe the same person".
# Catches typos (meilinggoh / meilingoh 0.75) and swapped word order on the spaced name
# (alex lim / lim alex 1.0), but not different people who share a first name (alexlim / alextan 0.33).
SIMILAR_NAME_THRESHOLD = 0.5
MIN_PREFIX_LEN = 4  # "moonyoung" vs "moonyoungsong", but not "tan" vs "tanahkow"


def find_similar_professors(db: Session, name: str, limit: int = 5) -> list[dict]:
    """
    Existing professors who may be the person called `name`, most likely first.
    match = "same" when the normalised names are identical, otherwise "similar".
    """
    key, words = normalize_name(name), name_words(name)
    if not key:
        return []

    same = Professor.name_key == key
    conditions = [
        same,
        func.similarity(Professor.name_key, key) >= SIMILAR_NAME_THRESHOLD,
        # Word-order blind: trigrams are taken per word on the spaced name
        func.similarity(Professor.name, words) >= SIMILAR_NAME_THRESHOLD,
    ]
    if len(key) >= MIN_PREFIX_LEN:
        conditions += [
            Professor.name_key.startswith(key),  # typed less than the stored name
            # typed more than the stored name; keys are [a-z0-9] only, so no LIKE wildcards
            (literal(key).startswith(Professor.name_key)) & (func.length(Professor.name_key) >= MIN_PREFIX_LEN),
        ]

    score = func.greatest(func.similarity(Professor.name_key, key), func.similarity(Professor.name, words))
    stmt = (
        professors_with_stats()
        .add_columns(same.label("is_same"))
        .where(or_(*conditions))
        .order_by(case((same, 0), else_=1), score.desc(), Professor.name)
        .limit(limit)
    )
    return [
        {**professor_to_dict(p, avg, count), "match": "same" if is_same else "similar"}
        for p, avg, count, is_same in db.execute(stmt)
    ]


@app.get("/professors/similar")
def similar_professors(name: str, db: Session = Depends(get_db)):
    """Used by the Add Professor form while typing. Declared before /professors/{professor_id}."""
    return {"items": find_similar_professors(db, name)}


@app.post("/professors", dependencies=[Depends(get_current_user)])
def create_professor(payload: ProfessorCreate, db: Session = Depends(get_db)):
    name = payload.name.strip()
    key = normalize_name(name)
    if not key:
        raise HTTPException(status_code=422, detail="Name must contain letters or digits")

    similar = find_similar_professors(db, name)
    if any(s["match"] == "same" for s in similar):
        raise HTTPException(
            status_code=409,
            detail={"message": "This professor is already on ProfRating", "similar": similar},
        )
    if similar and not payload.confirm_not_duplicate:
        raise HTTPException(
            status_code=409,
            detail={"message": "There may already be a page for this professor", "similar": similar},
        )

    prof = Professor(
        name=name,
        name_key=key,
        department=payload.department.strip() if payload.department else None,
        faculty=payload.faculty.strip() if payload.faculty else None,
    )
    db.add(prof)
    try:
        db.commit()
    except IntegrityError:
        # uq_professors_name_key: someone added the same name between our check and insert
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail={"message": "This professor is already on ProfRating", "similar": find_similar_professors(db, name)},
        )

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
    return {**professor_to_dict(p, avg, count), "modules": modules_taught(db, professor_id)}


@app.post("/professors/{professor_id}/reviews")
def create_review(
    professor_id: int,
    payload: ReviewCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if db.get(Professor, professor_id) is None:
        raise HTTPException(status_code=404, detail="Professor not found")

    if payload.replaces_deleted_review_id is not None:
        take_deleted_review(db, user, payload.replaces_deleted_review_id, professor_id)

    # No per-user limit: the same student may review a professor more than once
    review = Review(
        professor_id=professor_id,
        user_id=user.id,
        rating=payload.rating,
        module_code=payload.module_code.strip().upper() if payload.module_code else None,
        comment=payload.comment.strip() if payload.comment else None,
        academic_year=payload.academic_year,
        semester=payload.semester,
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
