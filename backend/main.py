from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from db import professors_col
from models import ProfessorCreate
from bson import ObjectId
from datetime import datetime, timezone
from typing import Optional
from fastapi import Path
from db import reviews_col  # 确保导入
from models import ReviewCreate

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"ok": True, "service": "backend"}

@app.post("/professors")
def create_professor(payload: ProfessorCreate):
    """
    Create a new professor.
    This endpoint is intentionally explicit in what it returns
    to avoid leaking database-internal fields (e.g. _id).
    """

    name = payload.name.strip()

    # 1. Check for duplicate professor (simple MVP rule)
    if professors_col.find_one({"name": name}):
        raise HTTPException(status_code=409, detail="Professor already exists")

    # 2. Build DB document (input -> DB layer)
    insert_doc = {
        "name": name,
        "department": payload.department.strip() if payload.department else None,
        "faculty": payload.faculty.strip() if payload.faculty else None,
    }

    # 3. Insert into MongoDB
    result = professors_col.insert_one(insert_doc)

    # 4. Build API response explicitly (DB -> API layer)
    return {
        "id": str(result.inserted_id),
        "name": insert_doc["name"],
        "department": insert_doc["department"],
        "faculty": insert_doc["faculty"],
    }

@app.get("/professors")
def list_professors(query: Optional[str] = None, limit: int = 50):
    """
    List professors. Supports basic name search via ?query=...
    limit is capped to avoid returning too many documents in one request.
    """
    safe_limit = max(1, min(limit, 200))

    mongo_filter = {}
    if query and query.strip():
        q = query.strip()
        mongo_filter = {"name": {"$regex": q, "$options": "i"}}

    cursor = (
        professors_col.find(mongo_filter, {"name": 1, "department": 1, "faculty": 1})
        .sort("name", 1)
        .limit(safe_limit)
    )

    results = []
    for doc in cursor:
        results.append(
            {
                "id": str(doc["_id"]),
                "name": doc.get("name"),
                "department": doc.get("department"),
                "faculty": doc.get("faculty"),
            }
        )

    return {"items": results, "count": len(results)}

def parse_object_id(id_str: str) -> ObjectId:
    if not ObjectId.is_valid(id_str):
        raise HTTPException(status_code=400, detail="Invalid id format")
    return ObjectId(id_str)

@app.post("/professors/{professor_id}/reviews")
def create_review(
    professor_id: str = Path(..., min_length=1),
    payload: ReviewCreate = None,
):
    prof_oid = parse_object_id(professor_id)

    # Ensure professor exists
    prof = professors_col.find_one({"_id": prof_oid})
    if not prof:
        raise HTTPException(status_code=404, detail="Professor not found")

    doc = {
        "professor_id": prof_oid,
        "rating": payload.rating,
        "module_code": payload.module_code.strip().upper() if payload.module_code else None,
        "comment": payload.comment.strip() if payload.comment else None,
        "created_at": datetime.now(timezone.utc),
    }

    result = reviews_col.insert_one(doc)

    return {
        "id": str(result.inserted_id),
        "professor_id": professor_id,
        "rating": doc["rating"],
        "module_code": doc["module_code"],
        "comment": doc["comment"],
        "created_at": doc["created_at"].isoformat(),
    }
@app.get("/professors/{professor_id}/reviews")
def list_reviews(professor_id: str, limit: int = 50, skip: int = 0):
    prof_oid = parse_object_id(professor_id)

    safe_limit = max(1, min(limit, 200))
    safe_skip = max(0, skip)

    cursor = (
        reviews_col.find({"professor_id": prof_oid})
        .sort("created_at", -1)
        .skip(safe_skip)
        .limit(safe_limit)
    )

    items = []
    for r in cursor:
        items.append(
            {
                "id": str(r["_id"]),
                "professor_id": professor_id,
                "rating": r.get("rating"),
                "module_code": r.get("module_code"),
                "comment": r.get("comment"),
                "created_at": r.get("created_at").isoformat() if r.get("created_at") else None,
            }
        )

    return {"items": items, "count": len(items)}


@app.get("/professors/{professor_id}")
def get_professor(professor_id: str):
    prof_oid = parse_object_id(professor_id)
    p = professors_col.find_one({"_id": prof_oid}, {"name": 1, "department": 1, "faculty": 1})
    if not p:
        raise HTTPException(status_code=404, detail="Professor not found")

    pipeline = [
        {"$match": {"professor_id": prof_oid}},
        {"$group": {"_id": "$professor_id", "avg_rating": {"$avg": "$rating"}, "count": {"$sum": 1}}},
    ]
    agg = list(reviews_col.aggregate(pipeline))
    if agg:
        avg_rating = agg[0].get("avg_rating")
        count = agg[0].get("count", 0)
    else:
        avg_rating = None
        count = 0

    return {
        "id": professor_id,
        "name": p.get("name"),
        "department": p.get("department"),
        "faculty": p.get("faculty"),
        "avg_rating": round(avg_rating, 2) if avg_rating is not None else None,
        "review_count": count,
    }


