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
        client.post(f"/professors/{a['id']}/reviews", json={"rating": rating})

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
    assert client.post(f"/professors/{p['id']}/reviews", json={"rating": 0}).status_code == 422
    assert client.post(f"/professors/{p['id']}/reviews", json={"rating": 6}).status_code == 422
    assert client.post(f"/professors/{p['id']}/reviews").status_code == 422
    assert client.post("/professors/999/reviews", json={"rating": 3}).status_code == 404
    assert client.get("/professors/not-a-number").status_code == 422


def test_reviews_newest_first_and_module_code_normalised(client):
    p = add_prof(client, "Dr. Delta")
    client.post(f"/professors/{p['id']}/reviews", json={"rating": 3, "module_code": " cs1101s "})
    client.post(f"/professors/{p['id']}/reviews", json={"rating": 5, "comment": "  great  "})

    items = client.get(f"/professors/{p['id']}/reviews").json()["items"]
    assert [r["rating"] for r in items] == [5, 3]
    assert items[0]["comment"] == "great"
    assert items[1]["module_code"] == "CS1101S"


def test_detail(client):
    p = add_prof(client, "Dr. Epsilon", faculty="SoC")
    client.post(f"/professors/{p['id']}/reviews", json={"rating": 4})
    detail = client.get(f"/professors/{p['id']}").json()
    assert detail == {
        "id": p["id"], "name": "Dr. Epsilon", "department": None, "faculty": "SoC",
        "avg_rating": 4.0, "review_count": 1,
    }
    assert client.get("/professors/999").status_code == 404
