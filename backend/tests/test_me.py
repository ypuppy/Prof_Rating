from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy import func, select, update

import me
from db import SessionLocal
from main import app
from tables import DeletedReview
from helpers import TERM


def setup_prof_with_reviews(client, name="Dr. Iota", ratings=(5, 3)):
    prof = client.post("/professors", json={"name": name}).json()
    reviews = [
        client.post(
            f"/professors/{prof['id']}/reviews",
            json={**TERM, "rating": r, "module_code": "CS2030S", "comment": f"{r} stars"},
        ).json()
        for r in ratings
    ]
    return prof, reviews


def test_my_reviews_lists_only_mine_with_professor(client, login):
    prof, mine = setup_prof_with_reviews(client)
    other = TestClient(app)
    login(other, "e9999999@u.nus.edu")
    other.post(f"/professors/{prof['id']}/reviews", json={**TERM, "rating": 1})

    items = client.get("/me/reviews").json()["items"]
    assert [r["id"] for r in items] == [mine[1]["id"], mine[0]["id"]]  # newest first
    assert items[0]["professor"] == {"id": prof["id"], "name": "Dr. Iota", "department": None, "faculty": None}


def test_me_endpoints_require_login(anon):
    assert anon.get("/me/reviews").status_code == 401
    assert anon.delete("/me/reviews/1").status_code == 401
    assert anon.get("/me/deleted-reviews").status_code == 401


def test_cannot_delete_someone_elses_review(client, login):
    prof, mine = setup_prof_with_reviews(client, ratings=(4,))
    other = TestClient(app)
    login(other, "e9999999@u.nus.edu")

    assert other.delete(f"/me/reviews/{mine[0]['id']}").status_code == 404
    assert client.get(f"/professors/{prof['id']}").json()["review_count"] == 1


def test_delete_moves_review_to_cache_and_out_of_public_stats(client, anon):
    prof, (five, three) = setup_prof_with_reviews(client)

    res = client.delete(f"/me/reviews/{five['id']}")
    assert res.status_code == 200
    cached = res.json()
    assert (cached["rating"], cached["comment"], cached["professor"]["id"]) == (5, "5 stars", prof["id"])
    # The term is cached too, so the rewrite form can be pre-filled with it
    assert (cached["academic_year"], cached["semester"]) == (TERM["academic_year"], TERM["semester"])

    # Gone everywhere public, and from my list
    detail = anon.get(f"/professors/{prof['id']}").json()
    assert (detail["review_count"], detail["avg_rating"]) == (1, 3.0)
    assert [r["id"] for r in anon.get(f"/professors/{prof['id']}/reviews").json()["items"]] == [three["id"]]
    listed = anon.get("/professors").json()["items"][0]
    assert listed["review_count"] == 1
    assert [r["id"] for r in client.get("/me/reviews").json()["items"]] == [three["id"]]

    # But cached for me
    assert [d["id"] for d in client.get("/me/deleted-reviews").json()["items"]] == [cached["id"]]

    # Deleting twice fails
    assert client.delete(f"/me/reviews/{five['id']}").status_code == 404


def test_rewrite_creates_new_review_and_clears_cache(client):
    prof, (five, _) = setup_prof_with_reviews(client)
    cached = client.delete(f"/me/reviews/{five['id']}").json()

    res = client.post(
        f"/professors/{prof['id']}/reviews",
        json={**TERM, "rating": 4, "module_code": "CS2030S", "comment": "Changed my mind", "replaces_deleted_review_id": cached["id"]},
    )
    assert res.status_code == 200
    assert res.json()["id"] != five["id"]
    assert client.get("/me/deleted-reviews").json()["items"] == []

    # The cached copy can only be used once
    again = client.post(
        f"/professors/{prof['id']}/reviews", json={**TERM, "rating": 4, "replaces_deleted_review_id": cached["id"]}
    )
    assert again.status_code == 404


def test_rewrite_must_target_same_professor_and_owner(client, login):
    prof, (five, _) = setup_prof_with_reviews(client)
    other_prof = client.post("/professors", json={"name": "Dr. Kappa"}).json()
    cached = client.delete(f"/me/reviews/{five['id']}").json()

    res = client.post(f"/professors/{other_prof['id']}/reviews", json={**TERM, "rating": 4, "replaces_deleted_review_id": cached["id"]})
    assert res.status_code == 400

    other = TestClient(app)
    login(other, "e9999999@u.nus.edu")
    res = other.post(f"/professors/{prof['id']}/reviews", json={**TERM, "rating": 4, "replaces_deleted_review_id": cached["id"]})
    assert res.status_code == 404

    # Failed attempts didn't consume it or create reviews
    assert len(client.get("/me/deleted-reviews").json()["items"]) == 1
    assert client.get(f"/professors/{prof['id']}").json()["review_count"] == 1


def test_discard_deletes_cache_permanently(client, login):
    prof, (five, _) = setup_prof_with_reviews(client)
    cached = client.delete(f"/me/reviews/{five['id']}").json()

    other = TestClient(app)
    login(other, "e9999999@u.nus.edu")
    assert other.delete(f"/me/deleted-reviews/{cached['id']}").status_code == 404

    assert client.delete(f"/me/deleted-reviews/{cached['id']}").status_code == 200
    assert client.get("/me/deleted-reviews").json()["items"] == []
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(DeletedReview)) == 0


def test_expired_cache_is_purged(client):
    prof, (five, _) = setup_prof_with_reviews(client)
    cached = client.delete(f"/me/reviews/{five['id']}").json()
    with SessionLocal() as db:
        db.execute(update(DeletedReview).values(expires_at=me.now() - timedelta(seconds=1)))
        db.commit()

    assert client.get("/me/deleted-reviews").json()["items"] == []
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(DeletedReview)) == 0
    res = client.post(f"/professors/{prof['id']}/reviews", json={**TERM, "rating": 4, "replaces_deleted_review_id": cached["id"]})
    assert res.status_code == 404
