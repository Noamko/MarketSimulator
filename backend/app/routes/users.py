from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..users import create_user, list_users

router = APIRouter()


class CreateUserRequest(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    starting_cash_cents: int = Field(ge=0)


@router.get("/users")
def get_users() -> list[dict]:
    return list_users()


@router.post("/users", status_code=201)
def post_user(req: CreateUserRequest) -> dict:
    try:
        return create_user(req.name, req.starting_cash_cents)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
