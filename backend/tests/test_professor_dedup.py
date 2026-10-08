from helpers import TERM


def add(client, name, **extra):
    return client.post("/professors", json={"name": name, **extra})


def test_same_name_after_normalising_is_always_rejected(client):
    assert add(client, "Dr. Moon-Young Song").status_code == 200
    for variant in ("moon young song", "Prof Moon Young Song", "MOONYOUNG SONG"):
        res = add(client, variant, confirm_not_duplicate=True)  # confirming doesn't help
        assert res.status_code == 409, variant
        detail = res.json()["detail"]
        assert detail["message"] == "This professor is already on ProfRating"
        assert detail["similar"][0]["name"] == "Dr. Moon-Young Song"
        assert detail["similar"][0]["match"] == "same"


def test_similar_name_needs_confirmation(client):
    assert add(client, "moon young song").status_code == 200

    res = add(client, "moonyoung")                      # prefix of the stored name
    assert res.status_code == 409
    assert res.json()["detail"]["similar"][0]["match"] == "similar"

    assert add(client, "moonyoung", confirm_not_duplicate=True).status_code == 200


def test_word_order_and_typos_are_similar(client):
    add(client, "Dr. Alex Lim")
    add(client, "Prof. Mei Ling Goh")
    for name in ("Lim Alex", "Mei Ling Go"):
        res = add(client, name)
        assert res.status_code == 409, name
        assert res.json()["detail"]["similar"][0]["match"] == "similar"


def test_unrelated_names_are_added_without_questions(client):
    add(client, "Dr. Alex Lim")
    for name in ("Alex Tan", "Tan", "Priya Menon"):
        assert add(client, name).status_code == 200, name


def test_similar_endpoint_ranks_same_first_and_includes_stats(client, anon):
    a = add(client, "moon young song").json()
    add(client, "moonyoung", confirm_not_duplicate=True)
    client.post(f"/professors/{a['id']}/reviews", json={**TERM, "rating": 4})

    items = anon.get("/professors/similar", params={"name": "Moon Young Song"}).json()["items"]
    assert [(i["name"], i["match"]) for i in items] == [
        ("moon young song", "same"),
        ("moonyoung", "similar"),
    ]
    assert items[0]["review_count"] == 1
    assert anon.get("/professors/similar", params={"name": "Someone Else"}).json()["items"] == []


def test_name_without_letters_or_digits_is_rejected(client):
    assert add(client, "!!!").status_code == 422
