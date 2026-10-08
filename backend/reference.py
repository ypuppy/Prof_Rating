"""
Autocomplete for faculties, departments and module codes (data from scripts/sync_nus_data.py).

  GET /reference/faculties?query=soc
  GET /reference/departments?query=comp sci&faculty=School of Computing
  GET /reference/modules?query=CH1

All public. Results are suggestions only: the forms still accept anything the user types.
"""
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session

from db import get_db
from tables import Department, Faculty, Module

router = APIRouter(prefix="/reference", tags=["reference"])

# pg_trgm word_similarity: 1.0 = exact word match. 0.4 still tolerates a typo or two ("compter")
FUZZY_THRESHOLD = 0.4
MAX_LIMIT = 20


def clamp(limit: int) -> int:
    return max(1, min(limit, MAX_LIMIT))


def name_rank(column, q: str):
    """0 = starts with the query, 1 = contains it, 2 = only a fuzzy match."""
    return case(
        (column.istartswith(q, autoescape=True), 0),
        (column.icontains(q, autoescape=True), 1),
        else_=2,
    )


@router.get("/faculties")
def search_faculties(query: str = "", limit: int = 10, db: Session = Depends(get_db)):
    q = query.strip()
    stmt = select(Faculty).limit(clamp(limit))
    if not q:
        stmt = stmt.order_by(Faculty.name)
    else:
        stmt = stmt.where(
            or_(
                Faculty.name.icontains(q, autoescape=True),
                Faculty.short_name.icontains(q, autoescape=True),  # "SoC", "FASS"
                func.word_similarity(q, Faculty.name) >= FUZZY_THRESHOLD,
            )
        ).order_by(
            # An exact short name ("cde") beats everything else
            case((func.lower(Faculty.short_name) == q.lower(), 0), else_=1),
            name_rank(Faculty.name, q),
            func.word_similarity(q, Faculty.name).desc(),
            Faculty.name,
        )
    items = [{"name": f.name, "short_name": f.short_name} for f in db.scalars(stmt)]
    return {"items": items}


@router.get("/departments")
def search_departments(
    query: str = "", faculty: Optional[str] = None, limit: int = 10, db: Session = Depends(get_db)
):
    q = query.strip()
    stmt = select(Department).limit(clamp(limit))

    # Departments in the faculty the user already picked come first
    order = [case((Department.faculty == faculty, 0), else_=1)] if faculty else []
    if q:
        stmt = stmt.where(
            or_(
                Department.name.icontains(q, autoescape=True),
                func.word_similarity(q, Department.name) >= FUZZY_THRESHOLD,
            )
        )
        order += [name_rank(Department.name, q), func.word_similarity(q, Department.name).desc()]
    stmt = stmt.order_by(*order, Department.name)

    items = [{"name": d.name, "faculty": d.faculty} for d in db.scalars(stmt)]
    return {"items": items}


@router.get("/modules")
def search_modules(query: str = "", limit: int = 10, db: Session = Depends(get_db)):
    q = query.strip()
    if not q:
        return {"items": []}

    code_prefix = Module.code.startswith(q.upper(), autoescape=True)  # served by ix_modules_code_prefix
    stmt = (
        select(Module)
        .where(
            or_(
                code_prefix,
                Module.title.icontains(q, autoescape=True),
                func.word_similarity(q, Module.title) >= 0.6,  # stricter: titles are long
            )
        )
        .order_by(
            case((code_prefix, 0), (Module.title.icontains(q, autoescape=True), 1), else_=2),
            Module.code,
        )
        .limit(clamp(limit))
    )
    items = [
        {"code": m.code, "title": m.title, "department": m.department}
        for m in db.scalars(stmt)
    ]
    return {"items": items}
