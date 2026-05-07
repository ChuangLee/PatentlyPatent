"""认证：mid-fi 一键切角色（与前端 mock 一致）"""
from fastapi import APIRouter, HTTPException

from ..schemas import LoginAsRequest, UserOut
from ..fixtures import DEMO_USERS

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login-as", response_model=UserOut)
def login_as(req: LoginAsRequest):
    user = next((u for u in DEMO_USERS if u.role == req.role), None)
    if not user:
        raise HTTPException(404, "no demo user for role")
    return UserOut.model_validate(user.__dict__, from_attributes=False)
