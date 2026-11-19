"""Auth request / response shapes."""

from uuid import UUID

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=200)


class UserView(BaseModel):
    id: UUID
    email: str
    name: str
    is_demo: bool


class DemoInfo(BaseModel):
    """Shown on the sign-in page outside prod so a visitor can try the product."""

    email: str
    password: str
