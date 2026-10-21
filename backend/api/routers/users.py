from fastapi import APIRouter, Depends
from models.user import User
from api.dependencies.auth import get_current_user

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me")
async def read_users_me(current_user: User = Depends(get_current_user)):
    """Get the currently logged in user."""
    return {
        "id": str(current_user.id),
        "email": current_user.email,
        "full_name": current_user.full_name,
        "is_active": current_user.is_active,
    }
