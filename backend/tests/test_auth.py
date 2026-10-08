from datetime import timedelta

from sqlalchemy import select, update

import auth
from db import SessionLocal
from tables import LoginCode, Review

EMAIL = "e1234567@u.nus.edu"


def test_rejects_non_nus_email(anon, sent_codes):
    for email in ("someone@gmail.com", "x@nus.edu.sg.evil.com", "@u.nus.edu", "not-an-email"):
        res = anon.post("/auth/request-code", json={"email": email})
        assert res.status_code == 400, email
    assert sent_codes == {}


def test_full_login_flow_and_logout(anon, sent_codes):
    assert anon.get("/auth/me").status_code == 401

    # Email is normalised, so a capitalised address logs into the same account
    assert anon.post("/auth/request-code", json={"email": "  E1234567@U.NUS.EDU "}).status_code == 200
    code = sent_codes[EMAIL]
    assert len(code) == 6 and code.isdigit()

    res = anon.post("/auth/verify", json={"email": EMAIL, "code": code})
    assert res.status_code == 200
    assert res.json()["email"] == EMAIL
    cookie = res.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie

    assert anon.get("/auth/me").json()["email"] == EMAIL

    # A code only works once
    assert anon.post("/auth/verify", json={"email": EMAIL, "code": code}).status_code == 400

    assert anon.post("/auth/logout").status_code == 200
    assert anon.get("/auth/me").status_code == 401


def test_code_is_never_stored_in_plain_text(anon, sent_codes):
    anon.post("/auth/request-code", json={"email": EMAIL})
    with SessionLocal() as db:
        stored = db.scalars(select(LoginCode.code_hash)).one()
    assert sent_codes[EMAIL] not in stored


def test_wrong_code_locks_after_max_attempts(anon, sent_codes):
    anon.post("/auth/request-code", json={"email": EMAIL})
    real = sent_codes[EMAIL]
    wrong = "000000" if real != "000000" else "111111"

    for _ in range(auth.MAX_ATTEMPTS - 1):
        res = anon.post("/auth/verify", json={"email": EMAIL, "code": wrong})
        assert res.json()["detail"] == "Incorrect code"
    res = anon.post("/auth/verify", json={"email": EMAIL, "code": wrong})
    assert "Too many wrong attempts" in res.json()["detail"]

    # Even the right code is now useless
    assert anon.post("/auth/verify", json={"email": EMAIL, "code": real}).status_code == 400


def test_expired_code_is_rejected(anon, sent_codes):
    anon.post("/auth/request-code", json={"email": EMAIL})
    with SessionLocal() as db:
        db.execute(update(LoginCode).values(expires_at=auth.now() - timedelta(seconds=1)))
        db.commit()
    res = anon.post("/auth/verify", json={"email": EMAIL, "code": sent_codes[EMAIL]})
    assert res.status_code == 400
    assert "expired" in res.json()["detail"]


def test_resend_cooldown_and_only_newest_code_works(anon, sent_codes):
    anon.post("/auth/request-code", json={"email": EMAIL})
    first = sent_codes[EMAIL]
    assert anon.post("/auth/request-code", json={"email": EMAIL}).status_code == 429

    # Pretend the first code was sent two minutes ago
    with SessionLocal() as db:
        db.execute(update(LoginCode).values(created_at=auth.now() - timedelta(minutes=2)))
        db.commit()
    assert anon.post("/auth/request-code", json={"email": EMAIL}).status_code == 200
    second = sent_codes[EMAIL]

    if first != second:
        assert anon.post("/auth/verify", json={"email": EMAIL, "code": first}).status_code == 400
    assert anon.post("/auth/verify", json={"email": EMAIL, "code": second}).status_code == 200


def test_failed_email_send_does_not_trigger_cooldown(anon, monkeypatch):
    def boom(*args):
        raise OSError("SMTP down")

    monkeypatch.setattr(auth, "send_login_code", boom)
    assert anon.post("/auth/request-code", json={"email": EMAIL}).status_code == 502

    monkeypatch.setattr(auth, "send_login_code", lambda *args: None)
    assert anon.post("/auth/request-code", json={"email": EMAIL}).status_code == 200


def test_writing_requires_login(anon, client):
    prof = client.post("/professors", json={"name": "Dr. Zeta"}).json()

    assert anon.post("/professors", json={"name": "Dr. Eta"}).status_code == 401
    assert anon.post(f"/professors/{prof['id']}/reviews", json={"rating": 4}).status_code == 401
    # Reading stays public
    assert anon.get("/professors").status_code == 200
    assert anon.get(f"/professors/{prof['id']}/reviews").status_code == 200


def test_same_user_can_review_a_professor_many_times_anonymously(client):
    prof = client.post("/professors", json={"name": "Dr. Theta"}).json()
    for rating in (5, 4, 3):
        res = client.post(
            f"/professors/{prof['id']}/reviews", json={"rating": rating, "module_code": "CS1101S"}
        )
        assert res.status_code == 200
        assert "user_id" not in res.json()

    items = client.get(f"/professors/{prof['id']}/reviews").json()["items"]
    assert len(items) == 3
    assert all("user_id" not in r for r in items)

    # The author is still recorded in the database
    me = client.get("/auth/me").json()
    with SessionLocal() as db:
        authors = set(db.scalars(select(Review.user_id)))
    assert authors == {me["id"]}
