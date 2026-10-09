"""
SQLAlchemy table definitions (DB layer).
API request/response shapes live in models.py.
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Professor(Base):
    __tablename__ = "professors"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120))
    # names.normalize_name(name): "Dr. Moon-Young Song" -> "moonyoungsong". Set by the app.
    name_key: Mapped[str] = mapped_column(String(120))
    department: Mapped[Optional[str]] = mapped_column(String(120))
    faculty: Mapped[Optional[str]] = mapped_column(String(120))
    # The department website's entry for this person, if we know it. One professor per entry.
    staff_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("staff_directory.id", ondelete="SET NULL"), unique=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    reviews: Mapped[list["Review"]] = relationship(
        back_populates="professor", passive_deletes=True
    )
    staff: Mapped[Optional["StaffMember"]] = relationship()

    __table_args__ = (
        # "Dr. Tan Ah Kow", "tan ah kow" and "Prof Tan Ah-Kow" count as the same professor
        Index("uq_professors_name_key", name_key, unique=True),
        # Fuzzy "is this the same person?" lookups on the normalised name
        Index(
            "ix_professors_name_key_trgm",
            name_key,
            postgresql_using="gin",
            postgresql_ops={"name_key": "gin_trgm_ops"},
        ),
        # Trigram index so ILIKE '%tan%' searches don't scan the whole table
        Index(
            "ix_professors_name_trgm",
            name,
            postgresql_using="gin",
            postgresql_ops={"name": "gin_trgm_ops"},
        ),
    )


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    # Always stored lowercased, so a plain unique index is enough
    email: Mapped[str] = mapped_column(String(254), unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class LoginCode(Base):
    """A one-time code emailed to someone trying to log in."""

    __tablename__ = "login_codes"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(254))
    # HMAC of the code, never the code itself
    code_hash: Mapped[str] = mapped_column(String(64))
    attempts: Mapped[int] = mapped_column(Integer, server_default="0")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    consumed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        # Serves "latest code for this email" and the resend rate limit
        Index("ix_login_codes_email_created", email, created_at.desc()),
    )


class UserSession(Base):
    """A logged-in browser. The cookie holds the token; we only store its hash."""

    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped[User] = relationship()


class Review(Base):
    __tablename__ = "reviews"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    professor_id: Mapped[int] = mapped_column(
        ForeignKey("professors.id", ondelete="CASCADE")
    )
    # Nullable: reviews imported from MongoDB have no author.
    # Never returned by the API, so reviews stay anonymous to other students.
    user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    rating: Mapped[int] = mapped_column(SmallInteger)
    module_code: Mapped[Optional[str]] = mapped_column(String(20))
    comment: Mapped[Optional[str]] = mapped_column(Text)
    # When the student took the class. AY2025/26 Sem 1 -> academic_year=2025, semester=1.
    # Nullable only because older reviews were written before this was asked; the API requires it.
    academic_year: Mapped[Optional[int]] = mapped_column(SmallInteger)
    semester: Mapped[Optional[int]] = mapped_column(SmallInteger)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    professor: Mapped[Professor] = relationship(back_populates="reviews")

    __table_args__ = (
        CheckConstraint("rating BETWEEN 1 AND 5", name="ck_reviews_rating_range"),
        # 1 = Sem 1, 2 = Sem 2, 3 = Special Term 1, 4 = Special Term 2
        CheckConstraint("semester BETWEEN 1 AND 4", name="ck_reviews_semester_range"),
        # Both or neither
        CheckConstraint("(academic_year IS NULL) = (semester IS NULL)", name="ck_reviews_term_complete"),
        # Serves "reviews for professor X, newest first"
        Index("ix_reviews_professor_created", professor_id, created_at.desc()),
    )


class DeletedReview(Base):
    """
    A review its author deleted, kept for a short time so they can rewrite it.
    Lives in its own table, so public queries on `reviews` never see it.
    """

    __tablename__ = "deleted_reviews"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    professor_id: Mapped[int] = mapped_column(ForeignKey("professors.id", ondelete="CASCADE"))
    rating: Mapped[int] = mapped_column(SmallInteger)
    module_code: Mapped[Optional[str]] = mapped_column(String(20))
    comment: Mapped[Optional[str]] = mapped_column(Text)
    academic_year: Mapped[Optional[int]] = mapped_column(SmallInteger)
    semester: Mapped[Optional[int]] = mapped_column(SmallInteger)
    original_created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

    professor: Mapped[Professor] = relationship()


# ---------- Reference data synced from NUSMods (scripts/sync_nus_data.py) ----------
# Only used for autocomplete suggestions; professors and reviews still accept free text.


class Faculty(Base):
    __tablename__ = "faculties"

    name: Mapped[str] = mapped_column(String(120), primary_key=True)
    short_name: Mapped[Optional[str]] = mapped_column(String(20))

    __table_args__ = (
        Index("ix_faculties_name_trgm", name, postgresql_using="gin", postgresql_ops={"name": "gin_trgm_ops"}),
    )


class Department(Base):
    __tablename__ = "departments"

    name: Mapped[str] = mapped_column(String(120), primary_key=True)
    faculty: Mapped[Optional[str]] = mapped_column(ForeignKey("faculties.name", ondelete="SET NULL"))

    __table_args__ = (
        Index("ix_departments_name_trgm", name, postgresql_using="gin", postgresql_ops={"name": "gin_trgm_ops"}),
    )


class Module(Base):
    __tablename__ = "modules"

    code: Mapped[str] = mapped_column(String(20), primary_key=True)
    title: Mapped[str] = mapped_column(String(300))
    faculty: Mapped[Optional[str]] = mapped_column(String(120))
    department: Mapped[Optional[str]] = mapped_column(String(120))

    __table_args__ = (
        # The primary key index can't serve LIKE 'CH%' under a non-C collation;
        # varchar_pattern_ops makes prefix searches use an index
        Index("ix_modules_code_prefix", code, postgresql_ops={"code": "varchar_pattern_ops"}),
        Index("ix_modules_title_trgm", title, postgresql_using="gin", postgresql_ops={"title": "gin_trgm_ops"}),
    )


class StaffMember(Base):
    """
    A person listed on a department's "faculty" web page (scripts/import_staff_page.py).
    Reference data: students search it when adding a professor, and linked professors show it.
    """

    __tablename__ = "staff_directory"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200))
    name_key: Mapped[str] = mapped_column(String(200))  # names.normalize_name(name)
    # Text, not String(n): these come from other people's pages, and some titles run long
    # ("Deputy Head & Senior Lecturer (Joint appointment with ...), Assistant Dean (...)")
    position: Mapped[Optional[str]] = mapped_column(Text)  # "Assistant Professor"
    roles: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default="{}")  # "Head of Department", home unit
    section: Mapped[Optional[str]] = mapped_column(Text)  # "Main Faculty", "Joint Faculty", ...
    department: Mapped[Optional[str]] = mapped_column(String(120))
    faculty: Mapped[Optional[str]] = mapped_column(String(120))
    research_areas: Mapped[Optional[str]] = mapped_column(Text)
    profile_urls: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default="{}")
    photo_url: Mapped[Optional[str]] = mapped_column(Text)
    bio: Mapped[Optional[str]] = mapped_column(Text)
    source_url: Mapped[str] = mapped_column(Text)  # the page this came from
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        # Re-importing a page updates people instead of duplicating them
        Index("uq_staff_directory_source_name", source_url, name_key, unique=True),
        Index("ix_staff_directory_name_key_trgm", name_key, postgresql_using="gin",
              postgresql_ops={"name_key": "gin_trgm_ops"}),
        Index("ix_staff_directory_name_trgm", name, postgresql_using="gin",
              postgresql_ops={"name": "gin_trgm_ops"}),
    )

