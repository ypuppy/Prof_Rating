from pydantic import BaseModel, Field
from typing import Optional

class ProfessorCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    department: Optional[str] = Field(default=None, max_length=120)
    faculty: Optional[str] = Field(default=None, max_length=120)

class ReviewCreate(BaseModel):
    rating: int = Field(ge=0, le=5)
    module_code: Optional[str] = Field(default=None, max_length=20)
    comment: Optional[str] = Field(default=None, max_length=2000)


    