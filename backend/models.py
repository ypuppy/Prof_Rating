from pydantic import BaseModel, Field, field_validator
from typing import Optional

from terms import current_academic_year

class ProfessorCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    department: Optional[str] = Field(default=None, max_length=120)
    faculty: Optional[str] = Field(default=None, max_length=120)

class ReviewCreate(BaseModel):
    rating: int = Field(ge=1, le=5)
    module_code: Optional[str] = Field(default=None, max_length=20)
    comment: Optional[str] = Field(default=None, max_length=1000)
    # When the class was taken: AY2025/26 Sem 1 -> academic_year=2025, semester=1
    academic_year: int = Field(ge=2000)
    # 1 = Sem 1, 2 = Sem 2, 3 = Special Term 1, 4 = Special Term 2
    semester: int = Field(ge=1, le=4)
    # Set when rewriting a review the user just deleted; clears it from the cache
    replaces_deleted_review_id: Optional[int] = None

    @field_validator("academic_year")
    @classmethod
    def not_in_the_future(cls, year: int) -> int:
        if year > current_academic_year():
            raise ValueError("Academic year can't be in the future")
        return year
