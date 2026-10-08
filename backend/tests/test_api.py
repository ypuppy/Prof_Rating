from helpers import TERM


def add_prof(client, name, **extra):
    res = client.post("/professors", json={"name": name, **extra})
    assert res.status_code == 200, res.text
    return res.json()


def test_create_professor_rejects_case_insensitive_duplicate(client):
    add_prof(client, "Dr. Tan Ah Kow", department="CS")
    assert client.post("/professors", json={"name": "dr. tan ah kow"}).status_code == 409


def test_list_includes_rating_stats_and_profs_without_reviews(client):
    a = add_prof(client, "Dr. Alpha")
    add_prof(client, "Dr. Beta")
    for rating in (5, 4):
        client.post(f"/professors/{a['id']}/reviews", json={**TERM, "rating": rating})

    items = {p["name"]: p for p in client.get("/professors").json()["items"]}
    assert items["Dr. Alpha"]["avg_rating"] == 4.5
    assert items["Dr. Alpha"]["review_count"] == 2
    assert items["Dr. Beta"]["avg_rating"] is None
    assert items["Dr. Beta"]["review_count"] == 0


def test_search_is_case_insensitive_and_treats_wildcards_literally(client):
    add_prof(client, "Dr. Tan")
    add_prof(client, "Prof 100% Real")

    def names(q):
        return [p["name"] for p in client.get("/professors", params={"query": q}).json()["items"]]

    assert names("TAN") == ["Dr. Tan"]
    assert names("%") == ["Prof 100% Real"]
    assert names("_") == []
    assert client.get("/professors", params={"query": "("}).status_code == 200


def test_review_validation(client):
    p = add_prof(client, "Dr. Gamma")
    assert client.post(f"/professors/{p['id']}/reviews", json={**TERM, "rating": 0}).status_code == 422
    assert client.post(f"/professors/{p['id']}/reviews", json={**TERM, "rating": 6}).status_code == 422
    assert client.post(f"/professors/{p['id']}/reviews").status_code == 422
    assert client.post("/professors/999/reviews", json={**TERM, "rating": 3}).status_code == 404
    assert client.get("/professors/not-a-number").status_code == 422


def test_reviews_newest_first_and_module_code_normalised(client):
    p = add_prof(client, "Dr. Delta")
    client.post(f"/professors/{p['id']}/reviews", json={**TERM, "rating": 3, "module_code": " cs1101s "})
    client.post(f"/professors/{p['id']}/reviews", json={**TERM, "rating": 5, "comment": "  great  "})

    items = client.get(f"/professors/{p['id']}/reviews").json()["items"]
    assert [r["rating"] for r in items] == [5, 3]
    assert items[0]["comment"] == "great"
    assert items[1]["module_code"] == "CS1101S"


def test_detail(client):
    p = add_prof(client, "Dr. Epsilon", faculty="SoC")
    client.post(f"/professors/{p['id']}/reviews", json={**TERM, "rating": 4})
    detail = client.get(f"/professors/{p['id']}").json()
    assert detail == {
        "id": p["id"], "name": "Dr. Epsilon", "department": None, "faculty": "SoC",
        "avg_rating": 4.0, "review_count": 1, "modules": [],
    }
    assert client.get("/professors/999").status_code == 404


def test_review_requires_valid_semester(client):
    from terms import current_academic_year

    p = add_prof(client, "Dr. Zeta")
    url = f"/professors/{p['id']}/reviews"
    assert client.post(url, json={"rating": 4}).status_code == 422                                   # missing
    assert client.post(url, json={"rating": 4, "academic_year": 2025}).status_code == 422            # half missing
    assert client.post(url, json={"rating": 4, "academic_year": 2025, "semester": 5}).status_code == 422
    future = current_academic_year() + 1
    res = client.post(url, json={"rating": 4, "academic_year": future, "semester": 1})
    assert res.status_code == 422
    assert "future" in res.text

    ok = client.post(url, json={"rating": 4, "academic_year": 2024, "semester": 3})  # AY24/25 Special Term 1
    assert ok.status_code == 200
    item = client.get(url).json()["items"][0]
    assert (item["academic_year"], item["semester"]) == (2024, 3)


def test_detail_lists_modules_taught_from_reviews(client):
    from db import SessionLocal
    from tables import Module

    with SessionLocal() as db:
        db.add(Module(code="CS2040S", title="Data Structures and Algorithms"))
        db.commit()

    p = add_prof(client, "Dr. Eta")
    url = f"/professors/{p['id']}/reviews"
    for code in ("cs2040s", "CS2040S", "CS1231S", None):
        client.post(url, json={**TERM, "rating": 4, "module_code": code})

    modules = client.get(f"/professors/{p['id']}").json()["modules"]
    assert modules == [
        {"code": "CS2040S", "title": "Data Structures and Algorithms", "review_count": 2},
        {"code": "CS1231S", "title": None, "review_count": 1},  # not in NUSMods data: no title
    ]

