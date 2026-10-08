"""
Merge a duplicate professor into another one.

Usage (from backend/):
    python scripts/merge_professors.py --keep 11 --merge 10                 # dry run: shows what would change
    python scripts/merge_professors.py --keep 11 --merge 10 --apply
    python scripts/merge_professors.py --keep 11 --merge 10 --name "Song Moon-Young" --apply

All reviews (and cached deleted reviews) of --merge move to --keep, empty department/faculty
fields on --keep are filled from --merge, then --merge is deleted. One transaction: all or nothing.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import func, select, update

from db import SessionLocal
from names import normalize_name
from tables import DeletedReview, Professor, Review


class MergeError(Exception):
    pass


def merge_professors(db, keep_id: int, merge_id: int, new_name: str = None) -> dict:
    """
    Does the merge inside the caller's transaction (caller commits or rolls back).
    Returns a summary of what changed.
    """
    if keep_id == merge_id:
        raise MergeError("--keep and --merge are the same professor")

    # Lock both rows so nobody reviews the one being deleted halfway through
    rows = {
        p.id: p
        for p in db.scalars(select(Professor).where(Professor.id.in_([keep_id, merge_id])).with_for_update())
    }
    for prof_id in (keep_id, merge_id):
        if prof_id not in rows:
            raise MergeError(f"Professor {prof_id} not found")
    keep, merge = rows[keep_id], rows[merge_id]

    summary = {
        "keep": {"id": keep.id, "name": keep.name, "department": keep.department, "faculty": keep.faculty},
        "merge": {"id": merge.id, "name": merge.name, "department": merge.department, "faculty": merge.faculty},
        "reviews_moved": db.scalar(select(func.count()).where(Review.professor_id == merge_id)),
        "deleted_reviews_moved": db.scalar(select(func.count()).where(DeletedReview.professor_id == merge_id)),
    }

    db.execute(update(Review).where(Review.professor_id == merge_id).values(professor_id=keep_id))
    db.execute(update(DeletedReview).where(DeletedReview.professor_id == merge_id).values(professor_id=keep_id))

    keep.department = keep.department or merge.department
    keep.faculty = keep.faculty or merge.faculty
    db.delete(merge)
    db.flush()  # free merge's name_key before a rename might take it

    if new_name:
        keep.name = new_name.strip()
        keep.name_key = normalize_name(keep.name)
    db.flush()  # surfaces a unique-name clash here rather than at commit

    summary["result"] = {"id": keep.id, "name": keep.name, "department": keep.department, "faculty": keep.faculty}
    return summary


def print_summary(s, applied):
    print(f"Keep  #{s['keep']['id']}: {s['keep']['name']!r} | {s['keep']['department']} | {s['keep']['faculty']}")
    print(f"Merge #{s['merge']['id']}: {s['merge']['name']!r} | {s['merge']['department']} | {s['merge']['faculty']}")
    print(f"Moves {s['reviews_moved']} review(s) and {s['deleted_reviews_moved']} cached deleted review(s)")
    r = s["result"]
    print(f"Result #{r['id']}: {r['name']!r} | {r['department']} | {r['faculty']}")
    print("Applied." if applied else "Dry run: nothing changed. Re-run with --apply to do it.")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--keep", type=int, required=True, help="id of the professor to keep")
    parser.add_argument("--merge", type=int, required=True, help="id of the duplicate to fold in and delete")
    parser.add_argument("--name", help="rename the kept professor, e.g. to the name on the department website")
    parser.add_argument("--apply", action="store_true", help="actually commit (default is a dry run)")
    args = parser.parse_args()

    with SessionLocal() as db:
        try:
            summary = merge_professors(db, args.keep, args.merge, args.name)
        except MergeError as e:
            sys.exit(f"Error: {e}")
        if args.apply:
            db.commit()
        else:
            db.rollback()
    print_summary(summary, args.apply)


if __name__ == "__main__":
    main()
