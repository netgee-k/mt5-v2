from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from . import crud, schemas, auth
from .database import get_db

router = APIRouter(prefix="/admin", tags=["admin"])

# Templates
templates = Jinja2Templates(directory="app/templates")

@router.get("/", response_class=HTMLResponse)
async def admin_dashboard(
    request: Request,
    current_user: schemas.UserInDB = Depends(auth.get_admin_user),
    db: Session = Depends(get_db)
):
    """Admin dashboard"""
    total_users = crud.count_users(db)
    recent_users = crud.get_users(db, limit=10)
    
    return templates.TemplateResponse("admin/dashboard.html", {
        "request": request,
        "user": current_user,
        "total_users": total_users,
        "recent_users": recent_users,
    })

@router.get("/users", response_class=HTMLResponse)
async def admin_users(
    request: Request,
    skip: int = 0,
    limit: int = 50,
    current_user: schemas.UserInDB = Depends(auth.get_admin_user),
    db: Session = Depends(get_db)
):
    """User management"""
    users = crud.get_users(db, skip=skip, limit=limit)
    total_users = crud.count_users(db)
    
    return templates.TemplateResponse("admin/users.html", {
        "request": request,
        "user": current_user,
        "users": users,
        "total_users": total_users,
        "skip": skip,
        "limit": limit,
    })