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


class Review(Base):
    __tablename__ = "reviews"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    professor_id: Mapped[int] = mapped_column(
        ForeignKey("professors.id", ondelete="CASCADE")
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
