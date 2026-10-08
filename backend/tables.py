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
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Professor(Base):
    __tablename__ = "professors"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120))
    department: Mapped[Optional[str]] = mapped_column(String(120))
    faculty: Mapped[Optional[str]] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    reviews: Mapped[list["Review"]] = relationship(
        back_populates="professor", passive_deletes=True
    )

    __table_args__ = (
        # "Dr. Tan" and "dr. tan" count as the same professor
        Index("uq_professors_name_lower", func.lower(name), unique=True),
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
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    professor: Mapped[Professor] = relationship(back_populates="reviews")

    __table_args__ = (
        CheckConstraint("rating BETWEEN 1 AND 5", name="ck_reviews_rating_range"),
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
