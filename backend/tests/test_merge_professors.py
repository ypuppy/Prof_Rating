import os
import sys

import pytest
from sqlalchemy import select

from db import SessionLocal
from helpers import TERM
from tables import DeletedReview, Professor, Review

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
from merge_professors import MergeError, merge_professors  # noqa: E402


@pytest.fixture
def duplicates(client):
    keep = client.post("/professors", json={"name": "moonyoung", "department": "Philosophy"}).json()
    dup = client.post(
        "/professors",
        json={"name": "moon young song", "faculty": "FASS", "confirm_not_duplicate": True},
    ).json()
    client.post(f"/professors/{keep['id']}/reviews", json={**TERM, "rating": 5})
    for rating in (4, 3):
        client.post(f"/professors/{dup['id']}/reviews", json={**TERM, "rating": rating})
    # One of dup's reviews is sitting in the deleted-review cache
    mine = client.get("/me/reviews").json()["items"]
    client.delete(f"/me/reviews/{next(r['id'] for r in mine if r['rating'] == 3)}")
    return keep["id"], dup["id"]


def test_merge_moves_everything_and_deletes_duplicate(duplicates, anon):
    keep_id, dup_id = duplicates
    with SessionLocal() as db:
        summary = merge_professors(db, keep_id, dup_id)
        db.commit()

    assert (summary["reviews_moved"], summary["deleted_reviews_moved"]) == (1, 1)
    detail = anon.get(f"/professors/{keep_id}").json()
    assert detail["review_count"] == 2
    assert (detail["department"], detail["faculty"]) == ("Philosophy", "FASS")  # empty faculty filled
    assert anon.get(f"/professors/{dup_id}").status_code == 404
    with SessionLocal() as db:
        assert db.scalar(select(DeletedReview.professor_id)) == keep_id


def test_merge_can_rename_and_updates_name_key(duplicates):
    keep_id, dup_id = duplicates
    with SessionLocal() as db:
        merge_professors(db, keep_id, dup_id, new_name="Assoc Prof Moon Young Song")
        db.commit()
        prof = db.get(Professor, keep_id)
        # The merged record's key was freed first, so taking it doesn't clash
        assert (prof.name, prof.name_key) == ("Assoc Prof Moon Young Song", "moonyoungsong")


def test_dry_run_changes_nothing(duplicates):
    keep_id, dup_id = duplicates
    with SessionLocal() as db:
        merge_professors(db, keep_id, dup_id)
        db.rollback()
    with SessionLocal() as db:
        assert db.get(Professor, dup_id) is not None
        assert len(db.scalars(select(Review).where(Review.professor_id == dup_id)).all()) == 1


def test_merge_rejects_bad_ids(duplicates):
    keep_id, _ = duplicates
    with SessionLocal() as db:
        with pytest.raises(MergeError):
            merge_professors(db, keep_id, keep_id)
        with pytest.raises(MergeError):
            merge_professors(db, keep_id, 999999)
