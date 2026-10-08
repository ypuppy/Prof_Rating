import os
import sys
from datetime import date

import pytest

from db import SessionLocal
from tables import Department, Faculty, Module

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
from sync_nus_data import build_reference_data  # noqa: E402
from terms import current_academic_year  # noqa: E402


@pytest.fixture
def reference_data():
    with SessionLocal() as db:
        db.add_all([
            Faculty(name="School of Computing", short_name="SoC"),
            Faculty(name="Faculty of Arts and Social Sciences", short_name="FASS"),
            Faculty(name="College of Design and Engineering", short_name="CDE"),
        ])
        db.flush()
        db.add_all([
            Department(name="Computer Science", faculty="School of Computing"),
            Department(name="Information Systems and Analytics", faculty="School of Computing"),
            Department(name="Chinese Studies", faculty="Faculty of Arts and Social Sciences"),
            Department(name="Electrical and Computer Engineering", faculty="College of Design and Engineering"),
        ])
        db.add_all([
            Module(code="CH1101E", title="Retelling Chinese Stories: Change and Continuity"),
            Module(code="CH2121", title="History of Chinese Literature"),
            Module(code="CS2040S", title="Data Structures and Algorithms"),
            Module(code="MA1521", title="Calculus for Computing"),
            Module(code="CS50%X", title="Odd code with a wildcard"),
            Module(code="PC1101", title="Frontiers of Physics"),
        ])
        db.commit()


def names(client, path, key="name", **params):
    return [item[key] for item in client.get(path, params=params).json()["items"]]


def test_module_prefix_search_is_case_insensitive(anon, reference_data):
    assert names(anon, "/reference/modules", "code", query="ch") == ["CH1101E", "CH2121"]
    assert names(anon, "/reference/modules", "code", query="CH11") == ["CH1101E"]
    assert names(anon, "/reference/modules", "code", query="") == []


def test_module_search_by_title_puts_code_matches_first(anon, reference_data):
    assert names(anon, "/reference/modules", "code", query="data structures") == ["CS2040S"]
    # "chinese" matches two titles; neither code starts with it
    assert names(anon, "/reference/modules", "code", query="chinese") == ["CH1101E", "CH2121"]


def test_module_search_treats_wildcards_literally(anon, reference_data):
    assert names(anon, "/reference/modules", "code", query="CS50%") == ["CS50%X"]
    assert names(anon, "/reference/modules", "code", query="%") == []


def test_faculty_search_by_short_name_name_or_typo(anon, reference_data):
    assert names(anon, "/reference/faculties", query="soc")[0] == "School of Computing"
    assert names(anon, "/reference/faculties", query="cde") == ["College of Design and Engineering"]
    assert names(anon, "/reference/faculties", query="computng") == ["School of Computing"]
    assert len(names(anon, "/reference/faculties", query="")) == 3


def test_department_fuzzy_search(anon, reference_data):
    assert names(anon, "/reference/departments", query="compter")[0] == "Computer Science"
    assert names(anon, "/reference/departments", query="chin") == ["Chinese Studies"]


def test_departments_in_chosen_faculty_come_first(anon, reference_data):
    got = names(anon, "/reference/departments", query="", faculty="School of Computing")
    assert got[:2] == ["Computer Science", "Information Systems and Analytics"]
    got = names(anon, "/reference/departments", query="comp", faculty="College of Design and Engineering")
    assert got[0] == "Electrical and Computer Engineering"


def test_build_reference_data_cleans_nusmods_input():
    module_info = [
        {"moduleCode": "cs2040s ", "title": "Data Structures and Algorithms",
         "faculty": "Computing", "department": "Computer Science"},
        {"moduleCode": "EL1101E", "title": "The Nature of Language",
         "faculty": "Arts and Social Science", "department": "English,Ling.andTheatre Studies"},
        {"moduleCode": "CS1010", "title": "Programming Methodology",
         "faculty": "Computing", "department": "SoC Dean's Office"},
        {"moduleCode": "CH1731", "title": "Department Exchange Course",
         "faculty": "Arts and Social Science", "department": "Chinese Studies"},
        # Physiology appears under two faculties; the one with more modules wins
        {"moduleCode": "PY1", "title": "A", "faculty": "Yong Loo Lin Sch of Medicine", "department": "Physiology"},
        {"moduleCode": "PY2", "title": "B", "faculty": "Yong Loo Lin Sch of Medicine", "department": "Physiology"},
        {"moduleCode": "PY3", "title": "C", "faculty": "Science", "department": "Physiology"},
    ]
    modules, departments, placeholders = build_reference_data(module_info)

    assert placeholders == ["CH1731"]
    by_code = {m["code"]: m for m in modules}
    assert "CS2040S" in by_code                                  # trimmed and uppercased
    assert by_code["CS2040S"]["faculty"] == "School of Computing"  # mapped to the official name
    assert by_code["CS1010"]["department"] is None               # dean's office isn't a department
    assert {d["name"]: d["faculty"] for d in departments} == {
        "Computer Science": "School of Computing",
        "English, Linguistics and Theatre Studies": "Faculty of Arts and Social Sciences",
        "Physiology": "Yong Loo Lin School of Medicine",
    }


def test_current_academic_year_starts_in_august():
    assert current_academic_year(date(2026, 10, 8)) == 2026
    assert current_academic_year(date(2026, 7, 31)) == 2025
    assert current_academic_year(date(2026, 8, 1)) == 2026


def test_short_module_query_only_matches_code_prefix(anon, reference_data):
    # "cs" appears inside "Physics", but a 2-letter query is treated as a code prefix only
    assert names(anon, "/reference/modules", "code", query="cs") == ["CS2040S", "CS50%X"]
    # From 3 characters on, titles are searched too
    assert names(anon, "/reference/modules", "code", query="phys") == ["PC1101"]

