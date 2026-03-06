from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
from datetime import timedelta
from typing import Optional

from services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])

auth_service = AuthService()


class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str


class RegisterResponse(BaseModel):
    id: int
    username: str
    email: str


class LoginRequest(BaseModel):
    email: str
    password: str
    username: str


class UserResponse(BaseModel):
    id: str
    username: str
    email: str
    role: str = "teacher"


@router.post("/register", response_model=RegisterResponse)
async def register(request: RegisterRequest):
    """Register a new user (demo implementation - accepts any credentials)"""
    user = auth_service.register_user(request.username, request.email, request.password)
    return RegisterResponse(
        id=user["id"],
        username=user["username"],
        email=user["email"]
    )


@router.post("/login")
async def login(request: Request):
    """Login and get access token."""
    data = await request.json()
    email = data.get("email")
    password = data.get("password")
    username = data.get("username")

    if not email or not password or not username:
        raise HTTPException(status_code=400, detail="Email, password, and username are required")

    user = auth_service.authenticate_user(email, password, username)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = auth_service.create_access_token(
        data={"sub": str(user["id"])},
        expires_delta=timedelta(minutes=60)
    )

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": user
    }


@router.get("/me", response_model=UserResponse)
async def get_me(request: Request):
    """Get current user info."""
    authorization = request.headers.get("Authorization")
    if not authorization:
        raise HTTPException(status_code=401, detail="Not authenticated")

    token = authorization.replace("Bearer ", "")
    payload = auth_service.decode_token(token)
    
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")

    user_id: str = payload.get("sub")
    username: str = payload.get("username")

    return UserResponse(
        id=user_id,
        username=username if username else "unknown",
        email=f"{username if username else 'unknown'}@example.com"
    )
