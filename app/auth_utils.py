# app/auth_utils.py
from fastapi import Request, Depends, HTTPException
from sqlalchemy.orm import Session
from .database import get_db
from . import crud
from .auth import verify_token

async def get_current_user_from_cookie(
    request: Request,
    db: Session = Depends(get_db)
):
    """Get current user from cookie - supports both regular and OAuth users"""
    access_token = request.cookies.get("access_token")
    
    if not access_token:
        return None
    
    payload = verify_token(access_token, "access")
    if not payload:
        return None
    
    email = payload.get("sub")
    if not email:
        return None
    
    # Get user from database
    user = crud.get_user_by_email(db, email)
    if not user or not user.is_active:
        return None
    
    # Check if user needs to verify email (skip for OAuth users)
    auth_method = payload.get("auth_method")
    if auth_method != "google" and not user.is_verified:
        return None
    
    return user

async def get_current_active_user_cookie(
    request: Request,
    db: Session = Depends(get_db)
):
    """Get current active user from cookies (requires authentication)"""
    from fastapi import status
    
    user = await get_current_user_from_cookie(request, db)
    
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    
    return user