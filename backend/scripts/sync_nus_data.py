"""
Sync NUS faculties, departments and modules (for autocomplete) from the public NUSMods API.

Usage (from backend/, after `alembic upgrade head`):
    python scripts/sync_nus_data.py                 # current academic year
    python scripts/sync_nus_data.py --year 2025-2026

Safe to re-run: rows are upserted, never deleted, so modules from past years stay searchable.

Departments come from the faculty/department NUSMods attaches to each module. The official
list at nus.edu.sg/about/departments sits behind a CAPTCHA, so it can't be fetched by a script.
"""
import argparse
import json
import os
import re
import sys
import urllib.request
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert

from db import SessionLocal
from tables import Department, Faculty, Module
from terms import current_academic_year

NUSMODS_URL = "https://api.nusmods.com/v2/{year}/moduleInfo.json"

# Hardcoded: (official name, short name, how NUSMods spells it)
FACULTIES = [
    ("Faculty of Arts and Social Sciences", "FASS", "Arts and Social Science"),
    ("Faculty of Science", "FoS", "Science"),
    ("College of Design and Engineering", "CDE", "College of Design and Engineering"),
    ("School of Computing", "SoC", "Computing"),
    ("NUS Business School", "BIZ", "NUS Business School"),
    ("Faculty of Law", "Law", "Law"),
    ("Yong Loo Lin School of Medicine", "YLLSoM", "Yong Loo Lin Sch of Medicine"),
    ("Faculty of Dentistry", "FoD", "Dentistry"),
    ("Saw Swee Hock School of Public Health", "SSHSPH", "SSH School of Public Health"),
    ("Lee Kuan Yew School of Public Policy", "LKYSPP", "LKY School of Public Policy"),
    ("Yong Siew Toh Conservatory of Music", "YSTCM", "YST Conservatory of Music"),
    ("Duke-NUS Medical School", "Duke-NUS", "Duke-NUS Medical School"),
    ("NUS College", "NUSC", "NUS College"),
    ("School of Continuing and Lifelong Education", "SCALE", "Cont and Lifelong Education"),
    ("NUS Graduate School", "NUSGS", "NUS Graduate School"),
]
FACULTY_BY_NUSMODS_NAME = {nusmods: official for official, _, nusmods in FACULTIES}

# NUSMods department names that are squashed or abbreviated
DEPARTMENT_RENAMES = {
    "English,Ling.andTheatre Studies": "English, Linguistics and Theatre Studies",
    "PharmacyandPharmaceuticalScience": "Pharmacy and Pharmaceutical Science",
}


# Placeholder codes for exchange/transfer credit ("Department Exchange Course", "External Course", ...).
# About 2,300 of them; nobody reviews these, and they bury real modules in the suggestions.
PLACEHOLDER_TITLE = re.compile(r"(exchange|external).*course", re.IGNORECASE)


def is_real_department(name):
    """Drop administrative units that NUSMods lists as a module's department."""
    if not name or name == "None":
        return False
    lowered = name.lower()
    return not ("dean's office" in lowered or "dean’s office" in lowered or "office of" in lowered)


def build_reference_data(module_info):
    """
    Pure transform of NUSMods moduleInfo -> rows to upsert. No network or DB, so it's unit-testable.
    Returns (modules, departments, placeholder_codes).
    """
    modules = []
    placeholder_codes = []
    # department -> Counter of faculties, because a few departments show up under two faculties
    department_faculties = {}

    for m in module_info:
        if PLACEHOLDER_TITLE.search(m["title"]):
            placeholder_codes.append(m["moduleCode"].strip().upper())
            continue
        faculty = FACULTY_BY_NUSMODS_NAME.get(m.get("faculty"))
        department = m.get("department")
        if is_real_department(department):
            department = DEPARTMENT_RENAMES.get(department, department)
        else:
            department = None

        modules.append({
            "code": m["moduleCode"].strip().upper(),
            "title": m["title"].strip()[:300],
            "faculty": faculty,
            "department": department,
        })
        if department and faculty:
            department_faculties.setdefault(department, Counter())[faculty] += 1

    departments = [
        # Pick the faculty that owns most of the department's modules
        {"name": name, "faculty": counts.most_common(1)[0][0]}
        for name, counts in sorted(department_faculties.items())
    ]
    return modules, departments, placeholder_codes


def nusmods_year(start_year):
    """2026 -> "2026-2027", the format NUSMods URLs use."""
    return f"{start_year}-{start_year + 1}"


def fetch_module_info(year):
    url = NUSMODS_URL.format(year=year)
    req = urllib.request.Request(url, headers={"User-Agent": "ProfRating data sync"})
    with urllib.request.urlopen(req, timeout=120) as res:
        return json.load(res)


def upsert(db, table, rows, key, update_cols, batch=1000):
    for i in range(0, len(rows), batch):
        stmt = insert(table).values(rows[i:i + batch])
        stmt = stmt.on_conflict_do_update(
            index_elements=[key], set_={c: stmt.excluded[c] for c in update_cols}
        )
        db.execute(stmt)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--year", default=nusmods_year(current_academic_year()), help="Academic year, e.g. 2026-2027")
    args = parser.parse_args()

    print(f"Downloading NUSMods module info for {args.year} ...")
    modules, departments, placeholder_codes = build_reference_data(fetch_module_info(args.year))

    with SessionLocal() as db:
        upsert(db, Faculty.__table__,
               [{"name": n, "short_name": s} for n, s, _ in FACULTIES], "name", ["short_name"])
        upsert(db, Department.__table__, departments, "name", ["faculty"])
        upsert(db, Module.__table__, modules, "code", ["title", "faculty", "department"])
        # Placeholders may have been stored by an earlier version of this script
        db.execute(delete(Module).where(Module.code.in_(placeholder_codes)))
        db.commit()

    print(f"Faculties: {len(FACULTIES)}, departments: {len(departments)}, modules: {len(modules)} "
          f"(skipped {len(placeholder_codes)} exchange placeholders)")


if __name__ == "__main__":
    main()
