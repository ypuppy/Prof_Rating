"""
One-off migration: copy professors and reviews from the old MongoDB into Postgres.

Usage (from backend/, after `alembic upgrade head`):
    MONGODB_URI=mongodb+srv://... python scripts/migrate_from_mongo.py

Refuses to run if the Postgres tables already have data, so it can't double-import.
Everything is inserted in a single transaction: either all rows land or none do.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pymongo import MongoClient
from sqlalchemy import func, select

from db import SessionLocal
from tables import Professor, Review


def main():
    mongo_uri = os.getenv("MONGODB_URI")
    if not mongo_uri:
        sys.exit("MONGODB_URI is missing")
    # tz_aware: Mongo stores UTC; keep it explicit so timestamptz gets the right moment
    mongo = MongoClient(mongo_uri, tz_aware=True)[os.getenv("MONGODB_DB", "nus_prof_rater")]

    with SessionLocal() as db:
        if db.scalar(select(func.count()).select_from(Professor)):
            sys.exit("Postgres already has professors; refusing to import twice")

        # Mongo ObjectId -> new Postgres id, so reviews can point at the right professor
        id_map = {}
        id_by_name = {}  # lower(name) -> Postgres id
        skipped_profs = merged_profs = 0

        for doc in mongo["professors"].find().sort("_id", 1):
            name = (doc.get("name") or "").strip()
            if not name:
                skipped_profs += 1
                continue
            # The old app allowed "Dr. Tan" and "dr. tan" side by side; Postgres won't.
            # Merge the duplicate into the first one so its reviews aren't lost.
            if name.lower() in id_by_name:
                id_map[doc["_id"]] = id_by_name[name.lower()]
                merged_profs += 1
                continue

            prof = Professor(
                name=name,
                department=doc.get("department"),
                faculty=doc.get("faculty"),
                # ObjectIds embed their creation time
                created_at=doc["_id"].generation_time,
            )
            db.add(prof)
            db.flush()  # assigns prof.id without committing
            id_map[doc["_id"]] = prof.id
            id_by_name[name.lower()] = prof.id

        imported_reviews = skipped_reviews = 0
        for doc in mongo["reviews"].find().sort("_id", 1):
            prof_id = id_map.get(doc.get("professor_id"))
            rating = doc.get("rating")
            # Orphaned reviews, or 0-star ratings the old backend accepted
            if prof_id is None or not isinstance(rating, int) or not 1 <= rating <= 5:
                skipped_reviews += 1
                continue

            comment = doc.get("comment")
            db.add(
                Review(
                    professor_id=prof_id,
                    rating=rating,
                    module_code=doc.get("module_code"),
                    comment=comment[:1000] if comment else None,
                    created_at=doc.get("created_at") or doc["_id"].generation_time,
                )
            )
            imported_reviews += 1

        db.commit()

    print(f"Professors: {len(id_by_name)} imported, {merged_profs} merged (duplicate name), {skipped_profs} skipped (blank name)")
    print(f"Reviews:    {imported_reviews} imported, {skipped_reviews} skipped (orphaned or invalid rating)")


if __name__ == "__main__":
    main()
