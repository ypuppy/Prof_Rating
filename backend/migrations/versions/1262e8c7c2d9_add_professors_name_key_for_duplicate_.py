"""add professors name_key for duplicate detection

Revision ID: 1262e8c7c2d9
Revises: 9a4acaf001b8
Create Date: 2026-10-08 20:33:03.538203

"""
from typing import Sequence, Union

import re
import unicodedata

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1262e8c7c2d9'
down_revision: Union[str, Sequence[str], None] = '9a4acaf001b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Frozen copy of names.normalize_name as of this migration, so later changes to
# names.py can't change what this migration did.
_HONORIFICS = (
    "professor", "prof", "associate", "assoc", "assistant", "asst", "a/p",
    "adjunct", "adj", "emeritus", "dr", "mr", "mrs", "ms", "mdm",
)
_HONORIFIC = re.compile(r"^(?:" + "|".join(re.escape(h) for h in _HONORIFICS) + r")(?:\.\s*|\s+|$)")
_NOT_ALNUM = re.compile(r"[^a-z0-9]+")


def _normalize_name(name):
    decomposed = unicodedata.normalize("NFKD", name)
    original = "".join(c for c in decomposed if not unicodedata.combining(c)).lower().strip()
    text = original
    while True:
        stripped = _HONORIFIC.sub("", text, count=1).lstrip()
        if stripped == text:
            break
        text = stripped
    return _NOT_ALNUM.sub("", text) or _NOT_ALNUM.sub("", original)


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("professors", sa.Column("name_key", sa.String(length=120), nullable=True))

    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT id, name FROM professors ORDER BY id")).all()
    seen = {}
    for prof_id, name in rows:
        key = _normalize_name(name)
        if key in seen:
            raise RuntimeError(
                f"Professors {seen[key]} and {prof_id} normalise to the same name ({key!r}). "
                f"Merge them first: python scripts/merge_professors.py --keep {seen[key]} --merge {prof_id} --apply"
            )
        seen[key] = prof_id
        conn.execute(sa.text("UPDATE professors SET name_key = :k WHERE id = :id"), {"k": key, "id": prof_id})

    op.alter_column("professors", "name_key", nullable=False)
    op.create_index("uq_professors_name_key", "professors", ["name_key"], unique=True)
    op.create_index(
        "ix_professors_name_key_trgm", "professors", ["name_key"],
        postgresql_using="gin", postgresql_ops={"name_key": "gin_trgm_ops"},
    )
    # name_key is stricter than lower(name), so the old index is redundant
    op.drop_index("uq_professors_name_lower", table_name="professors")


def downgrade() -> None:
    """Downgrade schema."""
    op.create_index("uq_professors_name_lower", "professors", [sa.literal_column("lower(name)")], unique=True)
    op.drop_index("ix_professors_name_key_trgm", table_name="professors")
    op.drop_index("uq_professors_name_key", table_name="professors")
    op.drop_column("professors", "name_key")
