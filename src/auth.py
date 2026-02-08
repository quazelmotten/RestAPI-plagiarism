from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
from datetime import datetime, timedelta, timezone
from typing import Optional
import jwt
from passlib.context import CryptContext
from database import get_async_session
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm

router = APIRouter(prefix="/auth", tags=["Authentication"])

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, "your-secret-key-change-in-production", algorithm="HS256")
    return encoded_jwt

@router.post("/login")
async def login(request: Request):
    data = await request.json()
    email = data.get("email")
    password = data.get("password")
    username = data.get("username")
    
    if not email or not password or not username:
        return {
            "detail": "Email, password, and username are required"
        }
    
    # Demo authentication - accept any credentials
    user = {
        "id": 1,
        "email": email,
        "username": username
    }
    
    token = create_access_token(
        data={"sub": str(user["id"])},
        expires_delta=timedelta(minutes=60)
    )
    
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": user}

@router.get("/me")
async def get_me(request: Request):
    authorization = request.headers.get("Authorization")
    if not authorization:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        token = authorization.replace("Bearer ", "")
        payload = jwt.decode(token, "your-secret-key-change-in-production", algorithms=["HS256"])
        user_id: str = payload.get("sub")
        username: str = payload.get("username")

        return {
            "id": user_id,
            "username": username if username else "unknown",
            "email": f"{username if username else 'unknown'}@example.com",
            "role": "teacher"
        }
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")