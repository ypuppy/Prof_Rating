"""
Link an existing professor to their staff directory entry.

    python scripts/link_professor.py --professor 11 --staff 17                       # dry run
    python scripts/link_professor.py --professor 11 --staff 17 --use-official-name --apply

--use-official-name also takes the website's name, department and faculty, so "moonyoung"
becomes "Moonyoung SONG" in Philosophy. Without it, only empty department/faculty are filled.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select

from db import SessionLocal
from names import normalize_name
from tables import Professor, StaffMember


class LinkError(Exception):
    pass


def link_professor(db, professor_id, staff_id, use_official_name=False):
    prof = db.get(Professor, professor_id, with_for_update=True)
    staff = db.get(StaffMember, staff_id)
    if prof is None:
        raise LinkError(f"Professor {professor_id} not found")
    if staff is None:
        raise LinkError(f"Staff entry {staff_id} not found")
    other = db.scalars(select(Professor).where(Professor.staff_id == staff_id, Professor.id != professor_id)).first()
    if other:
        raise LinkError(
            f"{staff.name!r} is already linked to professor #{other.id} {other.name!r}. "
            f"If they're the same person, merge them: python scripts/merge_professors.py --keep {other.id} --merge {prof.id}"
        )

    before = (prof.name, prof.department, prof.faculty)
    prof.staff_id = staff.id
    if use_official_name:
        prof.name, prof.name_key = staff.name, normalize_name(staff.name)
        prof.department = staff.department or prof.department
        prof.faculty = staff.faculty or prof.faculty
    else:
        prof.department = prof.department or staff.department
        prof.faculty = prof.faculty or staff.faculty
    db.flush()  # a rename onto another professor's name fails here, on the unique name_key
    return before, (prof.name, prof.department, prof.faculty)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--professor", type=int, required=True)
    parser.add_argument("--staff", type=int, required=True)
    parser.add_argument("--use-official-name", action="store_true")
    parser.add_argument("--apply", action="store_true", help="actually write (default is a dry run)")
    args = parser.parse_args()

    with SessionLocal() as db:
        try:
            before, after = link_professor(db, args.professor, args.staff, args.use_official_name)
        except LinkError as e:
            sys.exit(f"Error: {e}")
        db.commit() if args.apply else db.rollback()

    print(f"Professor #{args.professor}: {before} -> {after}")
    print("Applied." if args.apply else "Dry run: nothing written. Re-run with --apply.")


if __name__ == "__main__":
    main()
