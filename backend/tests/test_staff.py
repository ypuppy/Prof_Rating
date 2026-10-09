import os
import sys

import pytest
from sqlalchemy import select

from db import SessionLocal
from tables import Professor, StaffMember

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
from import_staff_page import import_people  # noqa: E402
from link_professor import LinkError, link_professor  # noqa: E402

URL = "https://fass.nus.edu.sg/philo/faculty/"


def person(name, **extra):
    return {"name": name, "position": "Lecturer", "roles": [], "section": "Main Faculty",
            "research_areas": "Ethics", "profile_urls": [], "photo_url": None, "bio": None, **extra}


def run_import(people):
    with SessionLocal() as db:
        report = import_people(db, people, URL, "Philosophy", "Faculty of Arts and Social Sciences")
        db.commit()
    return report


def staff_id(name):
    with SessionLocal() as db:
        return db.scalar(select(StaffMember.id).where(StaffMember.name == name))


def test_import_links_exact_matches_and_suggests_similar_ones(client):
    exact = client.post("/professors", json={"name": "Dr Tang Weng Hong"}).json()
    similar = client.post("/professors", json={"name": "moonyoung"}).json()

    report = run_import([person("TANG Weng Hong", position="Associate Professor"), person("Moonyoung SONG")])

    assert report["linked"] == [(exact["id"], "Dr Tang Weng Hong", "TANG Weng Hong")]
    assert [(p, s) for p, _, _, s in report["suggestions"]] == [(similar["id"], "Moonyoung SONG")]

    detail = client.get(f"/professors/{exact['id']}").json()
    assert detail["staff"]["position"] == "Associate Professor"
    assert detail["department"] == "Philosophy"  # empty field filled from the website
    assert client.get(f"/professors/{similar['id']}").json()["staff"] is None  # not linked without a human


def test_reimport_updates_instead_of_duplicating_and_reports_people_who_left(client):
    run_import([person("TANG Weng Hong"), person("John HOLBO")])
    report = run_import([person("TANG Weng Hong", position="Professor")])

    with SessionLocal() as db:
        rows = db.scalars(select(StaffMember).order_by(StaffMember.name)).all()
    assert [(s.name, s.position) for s in rows] == [("John HOLBO", "Lecturer"), ("TANG Weng Hong", "Professor")]
    assert report["gone"] == ["John HOLBO"]


def test_staff_search_is_typo_tolerant_and_shows_existing_professor(client, anon):
    run_import([person("QU Hsueh Ming"), person("TANG Weng Hong")])
    created = client.post("/professors", json={"name": "QU Hsueh Ming", "staff_id": staff_id("QU Hsueh Ming")}).json()

    items = anon.get("/staff/search", params={"query": "qu hseuh"}).json()["items"]
    assert [(i["name"], i["professor_id"]) for i in items] == [("QU Hsueh Ming", created["id"])]
    assert anon.get("/staff/search", params={"query": "tang"}).json()["items"][0]["professor_id"] is None
    assert anon.get("/staff/search", params={"query": "x"}).json()["items"] == []


def test_adding_from_directory_links_and_fills_department(client):
    run_import([person("Moonyoung SONG", photo_url="https://fass.nus.edu.sg/x.jpg")])
    sid = staff_id("Moonyoung SONG")

    res = client.post("/professors", json={"name": "Moonyoung SONG", "staff_id": sid})
    assert res.status_code == 200
    body = res.json()
    assert (body["department"], body["faculty"]) == ("Philosophy", "Faculty of Arts and Social Sciences")
    assert body["staff"]["photo_url"] == "https://fass.nus.edu.sg/x.jpg"

    # The same directory entry can't get a second professor page, whatever name is typed
    again = client.post("/professors", json={"name": "M Song", "staff_id": sid, "confirm_not_duplicate": True})
    assert again.status_code == 409
    assert again.json()["detail"]["similar"][0]["id"] == body["id"]

    assert client.post("/professors", json={"name": "Someone", "staff_id": 999999}).status_code == 422


def test_link_professor_with_official_name(client):
    prof = client.post("/professors", json={"name": "moonyoung", "department": "philosophy"}).json()
    run_import([person("Moonyoung SONG")])
    sid = staff_id("Moonyoung SONG")

    with SessionLocal() as db:
        before, after = link_professor(db, prof["id"], sid, use_official_name=True)
        db.commit()
    assert after == ("Moonyoung SONG", "Philosophy", "Faculty of Arts and Social Sciences")
    with SessionLocal() as db:
        assert db.get(Professor, prof["id"]).name_key == "moonyoungsong"

    other = client.post("/professors", json={"name": "Totally Different", "department": "X"}).json()
    with SessionLocal() as db:
        with pytest.raises(LinkError, match="already linked"):
            link_professor(db, other["id"], sid)


def test_department_names_from_crawler_are_normalised():
    from reparse_staff_pages import department_name

    assert department_name("Department of Chinese Studies(opens in new tab)") == "Chinese Studies"
    assert department_name("South Asian Studies Programme(opens in new tab)") == "South Asian Studies"
    assert department_name("Centre for Language Studies") == "Centre for Language Studies"


def test_json_import_handles_several_departments(tmp_path, anon):
    import argparse
    import json

    from import_staff_page import sources_from_args

    data = {"departments": [
        {"code": "cs", "department": "Chinese Studies", "faculty": "Faculty of Arts and Social Sciences",
         "url": "https://fass.nus.edu.sg/cs/faculty/", "people": [person("LIU Chen 劉晨")]},
        # The same person on a second department's page gets a second entry, with that department
        {"code": "ecs", "department": "Economics", "faculty": "Faculty of Arts and Social Sciences",
         "url": "https://fass.nus.edu.sg/ecs/department-faculty/", "people": [person("LIU Chen")]},
        {"code": "oop", "department": "Office of Programmes", "faculty": "x", "url": "u", "people": []},
    ]}
    path = tmp_path / "staff.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    args = argparse.Namespace(json=str(path), html_file=None, url=None, department=None, faculty=None)

    sources = sources_from_args(args, argparse.ArgumentParser())
    assert [s[0] for s in sources] == ["cs", "ecs"]  # departments without people are skipped
    with SessionLocal() as db:
        for _, people, url, department, faculty in sources:
            import_people(db, people, url, department, faculty)
        db.commit()

    items = anon.get("/staff/search", params={"query": "liu chen"}).json()["items"]
    assert sorted(i["department"] for i in items) == ["Chinese Studies", "Economics"]
