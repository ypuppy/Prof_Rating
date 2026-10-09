"""
Search the staff directory (people imported from department websites).

  GET /staff/search?query=moonyoung

Public. Each result says whether a professor page already exists for that person (professor_id),
so the Add Professor form can send the user there instead of creating a duplicate.
"""
from fastapi import APIRouter, Depends
from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session

from db import get_db
from names import name_words, normalize_name
from tables import Professor, StaffMember

router = APIRouter(prefix="/staff", tags=["staff"])

# word_similarity: how well the query matches the best part of the name. A typo still scores
# well ("qu hseuh" vs "QU Hsueh Ming" 0.56) while other people stay low (TANG Weng Hong 0.11).
SEARCH_THRESHOLD = 0.5


def staff_to_dict(s: StaffMember) -> dict:
    return {
        "id": s.id,
        "name": s.name,
        "position": s.position,
        "roles": s.roles or [],
        "section": s.section,
        "department": s.department,
        "faculty": s.faculty,
        "research_areas": s.research_areas,
        "profile_urls": s.profile_urls or [],
        "photo_url": s.photo_url,
        "bio": s.bio,
        "source_url": s.source_url,
    }


@router.get("/search")
def search_staff(query: str = "", limit: int = 8, db: Session = Depends(get_db)):
    key, words = normalize_name(query), name_words(query)
    if len(key) < 2:
        return {"items": []}

    contains = StaffMember.name_key.contains(key)  # key is [a-z0-9] only: no LIKE wildcards
    score = func.word_similarity(words, StaffMember.name)
    stmt = (
        select(StaffMember, Professor.id)
        .outerjoin(Professor, Professor.staff_id == StaffMember.id)
        .where(or_(contains, score >= SEARCH_THRESHOLD))
        .order_by(
            case((StaffMember.name_key.startswith(key), 0), (contains, 1), else_=2),
            score.desc(),
            StaffMember.name,
        )
        .limit(max(1, min(limit, 20)))
    )
    items = [{**staff_to_dict(s), "professor_id": prof_id} for s, prof_id in db.execute(stmt)]
    return {"items": items}
