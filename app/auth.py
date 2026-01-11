# app/auth.py - COMPLETE VERSION WITH ALL REQUIRED FUNCTIONS
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from jose import JWTError, jwt
from passlib.hash import argon2
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from .config import settings
from .database import get_db

# OAuth2 scheme for token authentication
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token", auto_error=False)

# Argon2 password hashing
def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return argon2.verify(plain_password, hashed_password)
    except Exception:
        return False

def get_password_hash(password: str) -> str:
    return argon2.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire, "type": "access"})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm="HS256")
    return encoded_jwt

def create_refresh_token(data: dict) -> str:
    expire = datetime.utcnow() + timedelta(minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES)
    to_encode = data.copy()
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm="HS256")

def create_verification_token(email: str) -> str:
    expire = datetime.utcnow() + timedelta(hours=settings.VERIFICATION_TOKEN_EXPIRE_HOURS)
    to_encode = {"email": email, "exp": expire, "type": "verify"}
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm="HS256")

def verify_token(token: str, token_type: str = "access") -> Optional[Dict[str, Any]]:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        if payload.get("type") != token_type:
            return None
        if "exp" not in payload:
            return None
        return payload
    except JWTError as e:
        print(f"JWT Error: {str(e)}")
        return None
    except Exception as e:
        print(f"Token verification error: {str(e)}")
        return None

# ===== AUTH DEPENDENCIES =====

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    """
    Get current user from JWT token
    """
    if not token:
        return None
    
    payload = verify_token(token, "access")
    if not payload:
        return None
    
    username: str = payload.get("sub")
    if username is None:
        return None
    
    # Import here to avoid circular imports
    from . import crud
    from .models import User
    
    # Get user from database
    user = crud.get_user_by_email(db, username)
    if user is None:
        return None
    
    return user

async def get_current_active_user(
    current_user = Depends(get_current_user)
):
    """
    Get current active user (requires authentication)
    """
    if current_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    
    return current_user

async def get_admin_user(
    current_user = Depends(get_current_active_user)
):
    """
    Dependency to verify that the current user is an admin.
    """
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator privileges required"
        )
    return current_user

async def get_superuser(
    current_user = Depends(get_current_active_user)
):
    """
    Dependency to verify that the current user is a superuser.
    """
    # Check if user is superuser (you might need to add this field to your User model)
    if not getattr(current_user, 'is_superuser', False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Superuser privileges required"
        )
    return current_user