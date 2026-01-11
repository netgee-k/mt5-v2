from fastapi import FastAPI, Request, Depends, HTTPException, Form, UploadFile, File, Query
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Optional
import calendar as cal
import json
import jwt
import logging

# Import your local modules
from app import crud, schemas, auth, admin, ai_service
from app.database import get_db, engine, Base
from app.mt5_client import MT5Client
from app.models import Trade, User, UserSettings, UserBadge, WeeklyReport, TradeChecklist, NewsAlert
from app.config import settings
from app.utils import send_email, generate_verification_email, generate_password_reset_email, save_screenshot

# Configure logging
logger = logging.getLogger(__name__)

# Create database tables
Base.metadata.create_all(bind=engine)
settings.init_dirs()

# Create FastAPI app
app = FastAPI(title=settings.APP_NAME, version=settings.VERSION)

# Import google_auth router AFTER creating the app
from app.routers import google_auth

# Include routers
app.include_router(google_auth.router, prefix="/auth", tags=["authentication"])
app.include_router(admin.router)

# Mount static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Templates
templates = Jinja2Templates(directory="app/templates")

# JWT Settings
SECRET_KEY = settings.SECRET_KEY
ALGORITHM = getattr(settings, 'ALGORITHM', 'HS256')

# ==================== AUTHENTICATION ROUTES ====================

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Login page"""
    return templates.TemplateResponse("login.html", {
        "request": request
    })

@app.post("/login")
async def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    """Handle login form"""
    user = crud.get_user_by_email(db, email)
    if not user or not auth.verify_password(password, user.hashed_password):
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Invalid email or password"
        })
    
    if not user.is_verified:
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Please verify your email first"
        })
    
    if not user.is_active:
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Account is deactivated"
        })
    
    # Create tokens
    access_token = auth.create_access_token(data={"sub": user.email})
    refresh_token = auth.create_refresh_token(data={"sub": user.email})
    
    # Set cookies
    response = RedirectResponse(url="/dashboard", status_code=302)
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        secure=False,
        samesite="lax"
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        max_age=settings.REFRESH_TOKEN_EXPIRE_MINUTES * 60,
        secure=False,
        samesite="lax"
    )
    
    return response

@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    """Register page"""
    return templates.TemplateResponse("register.html", {
        "request": request
    })

@app.post("/register")
async def register(
    request: Request,
    email: str = Form(...),
    username: str = Form(...),
    full_name: str = Form(None),
    password: str = Form(...),
    confirm_password: str = Form(...),
    db: Session = Depends(get_db)
):
    """Handle registration"""
    if password != confirm_password:
        return templates.TemplateResponse("register.html", {
            "request": request,
            "error": "Passwords do not match"
        })
    
    # Check if user exists
    if crud.get_user_by_email(db, email):
        return templates.TemplateResponse("register.html", {
            "request": request,
            "error": "Email already registered"
        })
    
    if crud.get_user_by_username(db, username):
        return templates.TemplateResponse("register.html", {
            "request": request,
            "error": "Username already taken"
        })
    
    # Create user
    user_create = schemas.UserCreate(
        email=email,
        username=username,
        full_name=full_name,
        password=password
    )
    
    user = crud.create_user(db, user_create)
    
    # Create verification token
    verification_token = auth.create_verification_token(email)
    
    # Send verification email
    verification_url = f"{request.base_url}verify-email?token={verification_token}"
    email_html = generate_verification_email(user.full_name or user.username, verification_url)
    
    send_email(
        to_email=user.email,
        subject="Verify your email",
        html_content=email_html
    )
    
    return templates.TemplateResponse("register.html", {
        "request": request,
        "success": "Registration successful! Please check your email to verify your account."
    })

@app.get("/verify-email", response_class=HTMLResponse)
async def verify_email(
    request: Request,
    token: str,
    db: Session = Depends(get_db)
):
    """Verify email"""
    payload = auth.verify_token(token, "verify")
    if not payload:
        return templates.TemplateResponse("message.html", {
            "request": request,
            "title": "Invalid Token",
            "message": "The verification token is invalid or expired."
        })
    
    email = payload.get("email")
    if not email:
        return templates.TemplateResponse("message.html", {
            "request": request,
            "title": "Invalid Token",
            "message": "The verification token is invalid."
        })
    
    user = crud.verify_user(db, email)
    if not user:
        return templates.TemplateResponse("message.html", {
            "request": request,
            "title": "Error",
            "message": "User not found."
        })
    
    return templates.TemplateResponse("message.html", {
        "request": request,
        "title": "Email Verified",
        "message": "Your email has been verified. You can now login."
    })

@app.get("/forgot-password", response_class=HTMLResponse)
async def forgot_password_page(request: Request):
    """Forgot password page"""
    return templates.TemplateResponse("forgot-password.html", {
        "request": request
    })

@app.post("/forgot-password")
async def forgot_password(
    request: Request,
    email: str = Form(...),
    db: Session = Depends(get_db)
):
    """Handle forgot password"""
    user = crud.get_user_by_email(db, email)
    if not user:
        # Don't reveal if user exists for security
        return templates.TemplateResponse("forgot-password.html", {
            "request": request,
            "success": "If the email exists, you will receive a password reset link."
        })
    
    # Create password reset token
    reset_token = auth.create_access_token(
        data={"sub": email},
        expires_delta=timedelta(hours=1)
    )
    
    # Save token to database (simplified - in production use a separate table)
    reset_url = f"{request.base_url}reset-password?token={reset_token}"
    email_html = generate_password_reset_email(user.full_name or user.username, reset_url)
    
    send_email(
        to_email=user.email,
        subject="Reset your password",
        html_content=email_html
    )
    
    return templates.TemplateResponse("forgot-password.html", {
        "request": request,
        "success": "If the email exists, you will receive a password reset link."
    })

@app.get("/reset-password", response_class=HTMLResponse)
async def reset_password_page(request: Request, token: str):
    """Reset password page"""
    return templates.TemplateResponse("reset-password.html", {
        "request": request,
        "token": token
    })

@app.post("/reset-password")
async def reset_password(
    request: Request,
    token: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
    db: Session = Depends(get_db)
):
    """Handle password reset"""
    if password != confirm_password:
        return templates.TemplateResponse("reset-password.html", {
            "request": request,
            "token": token,
            "error": "Passwords do not match"
        })
    
    payload = auth.verify_token(token, "access")
    if not payload:
        return templates.TemplateResponse("message.html", {
            "request": request,
            "title": "Invalid Token",
            "message": "The reset token is invalid or expired."
        })
    
    email = payload.get("sub")
    if not email:
        return templates.TemplateResponse("message.html", {
            "request": request,
            "title": "Invalid Token",
            "message": "The reset token is invalid."
        })
    
    user = crud.reset_password(db, email, password)
    if not user:
        return templates.TemplateResponse("message.html", {
            "request": request,
            "title": "Error",
            "message": "User not found."
        })
    
    return templates.TemplateResponse("message.html", {
        "request": request,
        "title": "Password Reset",
        "message": "Your password has been reset. You can now login with your new password."
    })

@app.get("/logout")
async def logout():
    """Logout user"""
    response = RedirectResponse(url="/login")
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")
    return response

# ==================== MIDDLEWARE FOR AUTH ====================

async def get_current_user_from_cookie(request: Request, db: Session = Depends(get_db)):
    """Get current user from cookie - CLEAN VERSION"""
    access_token = request.cookies.get("access_token")
    
    if not access_token:
        return None
    
    try:
        payload = auth.verify_token(access_token, "access")
        
        if not payload:
            return None
        
        email = payload.get("sub")
        if not email:
            return None
        
        user = db.query(User).filter(User.email == email).first()
        
        if not user or not user.is_active:
            return None
        
        return user
        
    except Exception as e:
        return None

# ==================== PROTECTED ROUTES ====================

@app.get("/", response_class=HTMLResponse)
async def home_page(request: Request, db: Session = Depends(get_db)):
    """Home page - redirects to dashboard or login"""
    user = await get_current_user_from_cookie(request, db)
    if user:
        return RedirectResponse(url="/dashboard")
    return RedirectResponse(url="/login")

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_cookie)
):
    """Dashboard page"""
    if not current_user:
        return RedirectResponse(url="/login")
    
    stats = crud.get_trade_stats(db, current_user.id)
    recent_trades = crud.get_trades(db, current_user.id, limit=10)
    symbol_stats = crud.get_symbol_stats(db, current_user.id)
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "user": current_user,
        "stats": stats,
        "recent_trades": recent_trades,
        "symbol_stats": symbol_stats,
        "today": datetime.now().date()
    })

@app.get("/calendar", response_class=HTMLResponse)
async def calendar_page(
    request: Request,
    year: Optional[int] = None,
    month: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_cookie)
):
    """Calendar page"""
    if not current_user:
        return RedirectResponse(url="/login")
    
    today = datetime.now().date()
    year = year or today.year
    month = month or today.month
    
    # Get calendar
    month_cal = cal.monthcalendar(year, month)
    
    # Get trades for month
    first_day = datetime(year, month, 1).date()
    if month == 12:
        last_day = datetime(year + 1, 1, 1).date() - timedelta(days=1)
    else:
        last_day = datetime(year, month + 1, 1).date() - timedelta(days=1)
    
    trades = db.query(Trade).filter(
        Trade.user_id == current_user.id,
        Trade.time >= first_day,
        Trade.time <= last_day
    ).all()
    
    # Prepare calendar data
    month_data = []
    for week in month_cal:
        week_data = []
        for day in week:
            if day == 0:
                week_data.append(None)
            else:
                date = datetime(year, month, day).date()
                day_trades = [t for t in trades if t.time.date() == date]
                
                if day_trades:
                    profit = sum(t.profit for t in day_trades)
                    win_count = sum(1 for t in day_trades if t.win)
                    total = len(day_trades)
                    win_rate = (win_count / total * 100) if total > 0 else 0
                    
                    week_data.append({
                        'day': day,
                        'date': date,
                        'count': total,
                        'profit': profit,
                        'win_rate': win_rate,
                        'is_today': date == today,
                    })
                else:
                    week_data.append({
                        'day': day,
                        'date': date,
                        'count': 0,
                        'profit': 0,
                        'win_rate': 0,
                        'is_today': date == today,
                    })
        month_data.append(week_data)
    
    month_stats = crud.get_trade_stats(
        db,
        current_user.id,
        start_date=first_day,
        end_date=last_day
    )
    
    return templates.TemplateResponse("calendar.html", {
        "request": request,
        "user": current_user,
        "year": year,
        "month": month,
        "month_name": cal.month_name[month],
        "calendar": month_data,
        "month_stats": month_stats,
        "prev_month": month - 1 if month > 1 else 12,
        "prev_year": year if month > 1 else year - 1,
        "next_month": month + 1 if month < 12 else 1,
        "next_year": year if month < 12 else year + 1,
        "today": today,
    })

@app.get("/stats", response_class=HTMLResponse)
async def stats_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_cookie)
):
    """Statistics page"""
    if not current_user:
        return RedirectResponse(url="/login")
    
    today = datetime.now().date()
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)
    
    overall_stats = crud.get_trade_stats(db, current_user.id)
    weekly_stats = crud.get_trade_stats(db, current_user.id, start_date=week_ago)
    monthly_stats = crud.get_trade_stats(db, current_user.id, start_date=month_ago)
    symbol_stats = crud.get_symbol_stats(db, current_user.id)
    hourly_stats = crud.get_hourly_stats(db, current_user.id)
    
    return templates.TemplateResponse("stats.html", {
        "request": request,
        "user": current_user,
        "today": today,
        "overall_stats": overall_stats,
        "weekly_stats": weekly_stats,
        "monthly_stats": monthly_stats,
        "symbol_stats": symbol_stats,
        "hourly_stats": hourly_stats,
    })

@app.get("/trades", response_class=HTMLResponse)
async def trades_page(
    request: Request,
    skip: int = 0,
    limit: int = 50,
    symbol: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_cookie)
):
    """Trades page"""
    if not current_user:
        return RedirectResponse(url="/login")
    
    query = db.query(Trade).filter(Trade.user_id == current_user.id).order_by(Trade.time.desc())
    
    if symbol:
        query = query.filter(Trade.symbol == symbol)
    
    total_trades = query.count()
    trades = query.offset(skip).limit(limit).all()
    
    symbols = db.query(Trade.symbol).filter(Trade.user_id == current_user.id).distinct().all()
    
    return templates.TemplateResponse("trades.html", {
        "request": request,
        "user": current_user,
        "trades": trades,
        "total_trades": total_trades,
        "symbols": [s[0] for s in symbols],
        "current_symbol": symbol,
        "skip": skip,
        "limit": limit,
    })

@app.get("/settings", response_class=HTMLResponse)
async def settings_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_cookie)
):
    """Settings page"""
    if not current_user:
        return RedirectResponse(url="/login")
    
    return templates.TemplateResponse("settings.html", {
        "request": request,
        "user": current_user
    })

@app.post("/settings/profile")
async def update_profile(
    request: Request,
    username: str = Form(None),
    full_name: str = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_cookie)
):
    """Update profile information"""
    if not current_user:
        return RedirectResponse(url="/login")
    
    try:
        # Create user update with only the fields we want to update
        update_data = {}
        if username is not None:
            update_data["username"] = username
        if full_name is not None:
            update_data["full_name"] = full_name
        
        # Only update if there's something to update
        if update_data:
            user_update = schemas.UserUpdate(**update_data)
            updated_user = crud.update_user(db, current_user.id, user_update)
            user_for_template = updated_user
        else:
            user_for_template = current_user
        
        return templates.TemplateResponse("settings.html", {
            "request": request,
            "user": user_for_template,
            "success": "Profile updated successfully!"
        })
    except Exception as e:
        return templates.TemplateResponse("settings.html", {
            "request": request,
            "user": current_user,
            "error": f"Error updating profile: {str(e)}"
        })

@app.post("/settings/mt5")
async def update_mt5(
    request: Request,
    mt5_server: str = Form(None),
    mt5_login: str = Form(None),
    mt5_password: str = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_cookie)
):
    """Update MT5 credentials"""
    if not current_user:
        return RedirectResponse(url="/login")
    
    try:
        # Track updates
        updated = False
        
        # Handle MT5 Server
        if mt5_server is not None:
            mt5_server = mt5_server.strip()
            if mt5_server == "":
                if current_user.mt5_server is not None:
                    current_user.mt5_server = None
                    updated = True
            else:
                if current_user.mt5_server != mt5_server:
                    current_user.mt5_server = mt5_server
                    updated = True
        
        # Handle MT5 Login
        if mt5_login is not None:
            mt5_login = mt5_login.strip()
            if mt5_login == "":
                if current_user.mt5_login is not None:
                    current_user.mt5_login = None
                    updated = True
            else:
                try:
                    login_value = int(mt5_login)
                    if current_user.mt5_login != login_value:
                        current_user.mt5_login = login_value
                        updated = True
                except ValueError:
                    return templates.TemplateResponse("settings.html", {
                        "request": request,
                        "user": current_user,
                        "error": "MT5 login must be a valid number (digits only)"
                    })
        
        # Handle MT5 Password
        if mt5_password is not None:
            mt5_password = mt5_password.strip()
            if mt5_password == "":
                if current_user.mt5_password is not None:
                    current_user.mt5_password = None
                    updated = True
            else:
                if current_user.mt5_password != mt5_password:
                    current_user.mt5_password = mt5_password
                    updated = True
        
        # Save to database if there were updates
        if updated:
            db.add(current_user)
            db.commit()
            db.refresh(current_user)
            success_msg = "MT5 credentials updated successfully!"
        else:
            success_msg = "No changes detected"
        
        return templates.TemplateResponse("settings.html", {
            "request": request,
            "user": current_user,
            "success": success_msg
        })
        
    except Exception as e:
        db.rollback()
        return templates.TemplateResponse("settings.html", {
            "request": request,
            "user": current_user,
            "error": f"Error updating MT5 credentials: {str(e)}"
        })

@app.post("/settings/preferences")
async def update_preferences(
    request: Request,
    theme: str = Form(None),
    timezone: str = Form(None),
    chart_theme: str = Form(None),
    chart_type: str = Form(None),
    show_grid: bool = Form(False),
    show_volume: bool = Form(False),
    email_notifications: bool = Form(False),
    trade_alerts: bool = Form(False),
    report_frequency: str = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_cookie)
):
    """Update user preferences"""
    if not current_user:
        return RedirectResponse(url="/login")
    
    try:
        # First, get or create user settings
        user_settings = crud.get_user_settings(db, current_user.id)
        
        # Create settings update
        settings_data = {}
        if chart_theme is not None:
            settings_data["chart_theme"] = chart_theme
        if chart_type is not None:
            settings_data["chart_type"] = chart_type
        if show_grid is not None:
            settings_data["show_grid"] = show_grid
        if show_volume is not None:
            settings_data["show_volume"] = show_volume
        if email_notifications is not None:
            settings_data["email_notifications"] = email_notifications
        if trade_alerts is not None:
            settings_data["trade_alerts"] = trade_alerts
        if report_frequency is not None:
            settings_data["report_frequency"] = report_frequency
        
        # Update user settings
        if settings_data:
            updated_settings = crud.update_user_settings(db, current_user.id, schemas.UserSettingsUpdate(**settings_data))
        
        # Update user theme and timezone
        user_update_data = {}
        if theme:
            user_update_data["theme"] = theme
        if timezone:
            user_update_data["timezone"] = timezone
        
        if user_update_data:
            user_update = schemas.UserUpdate(**user_update_data)
            updated_user = crud.update_user(db, current_user.id, user_update)
        else:
            updated_user = current_user
        
        # Refresh to get settings
        db.refresh(updated_user)
        
        return templates.TemplateResponse("settings.html", {
            "request": request,
            "user": updated_user,
            "success": "Preferences updated successfully!"
        })
    except Exception as e:
        return templates.TemplateResponse("settings.html", {
            "request": request,
            "user": current_user,
            "error": f"Error updating preferences: {str(e)}"
        })

@app.post("/settings/security")
async def update_security(
    request: Request,
    current_password: str = Form(None),
    new_password: str = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_cookie)
):
    """Change password (requires current password)"""
    if not current_user:
        return RedirectResponse(url="/login")
    
    try:
        if not current_password or not new_password:
            return templates.TemplateResponse("settings.html", {
                "request": request,
                "user": current_user,
                "error": "Both current and new password are required"
            })
        
        if len(new_password) < 8:
            return templates.TemplateResponse("settings.html", {
                "request": request,
                "user": current_user,
                "error": "New password must be at least 8 characters"
            })
        
        # Create user update with password change
        user_update = schemas.UserUpdate(
            current_password=current_password,
            password=new_password
        )
        
        updated_user = crud.update_user(db, current_user.id, user_update)
        
        return templates.TemplateResponse("settings.html", {
            "request": request,
            "user": updated_user,
            "success": "Password changed successfully! Please login again."
        })
    except Exception as e:
        return templates.TemplateResponse("settings.html", {
            "request": request,
            "user": current_user,
            "error": f"Error changing password: {str(e)}"
        })

@app.get("/sync", response_class=HTMLResponse)
async def sync_page(
    request: Request,
    current_user: User = Depends(get_current_user_from_cookie)
):
    """Sync page for manual MT5 sync"""
    if not current_user:
        return RedirectResponse(url="/login")
    
    return templates.TemplateResponse("sync.html", {
        "request": request,
        "user": current_user
    })

@app.post("/sync")
async def sync_post(
    request: Request,
    days: int = Form(30),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_cookie)
):
    """Handle manual sync from form - FIXED to return JSON for AJAX"""
    if not current_user:
        return JSONResponse({"success": False, "error": "Not authenticated"})
    
    # Check if user has MT5 credentials
    if not current_user.mt5_server or not current_user.mt5_login or not current_user.mt5_password:
        return JSONResponse({
            "success": False,
            "error": "Please set your MT5 credentials in Settings first"
        })
    
    try:
        mt5 = MT5Client(
            server=current_user.mt5_server,
            login=current_user.mt5_login,
            password=current_user.mt5_password
        )
        trades = mt5.sync_trades(days=days)
        
        created = 0
        for trade in trades:
            crud.create_or_update_trade(db, trade, current_user.id)
            created += 1
        
        mt5.disconnect()
        
        # Get updated count
        total_in_db = db.query(Trade).filter(Trade.user_id == current_user.id).count()
        
        return JSONResponse({
            "success": True,
            "message": f"Successfully synced {created} trades from MT5",
            "synced_trades": created,
            "total_in_db": total_in_db
        })
        
    except Exception as e:
        logger.error(f"Sync failed: {e}")
        return JSONResponse({
            "success": False,
            "error": f"Sync failed: {str(e)}"
        })

# ==================== API ENDPOINTS ====================

@app.get("/api/trades")
async def read_trades_api(
    request: Request,
    skip: int = 0,
    limit: int = 100,
    symbol: Optional[str] = None,
    type: Optional[str] = None,
    win: Optional[bool] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_cookie)
):
    """API endpoint for reading trades (returns JSON)"""
    if not current_user:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    
    try:
        # Build query
        query = db.query(Trade).filter(Trade.user_id == current_user.id)
        
        # Apply filters
        if symbol:
            query = query.filter(Trade.symbol == symbol)
        if type:
            query = query.filter(Trade.type == type)
        if win is not None:
            if win:
                query = query.filter(Trade.profit > 0)
            else:
                query = query.filter(Trade.profit <= 0)
        
        # Get total count
        total_trades = query.count()
        
        # Get paginated trades
        trades = query.order_by(Trade.time.desc()).offset(skip).limit(limit).all()
        
        # Convert to list of dictionaries
        trades_list = []
        for trade in trades:
            trades_list.append({
                "id": trade.id,
                "ticket": trade.ticket,
                "time": trade.time.isoformat() if trade.time else None,
                "symbol": trade.symbol,
                "type": trade.type,
                "volume": trade.volume,
                "entry_price": trade.entry_price,
                "exit_price": getattr(trade, 'exit_price', trade.entry_price),
                "profit": trade.profit,
                "commission": getattr(trade, 'commission', 0.0),
                "swap": getattr(trade, 'swap', 0.0),
                "pips": getattr(trade, 'pips', 0.0),
                "win": getattr(trade, 'win', trade.profit > 0),
                "win_rate": getattr(trade, 'win_rate', 0.0),
                "notes": getattr(trade, 'notes', None),
                "tags": getattr(trade, 'tags', None),
                "screenshot": getattr(trade, 'screenshot', None),
                "sl": getattr(trade, 'sl', None),
                "tp": getattr(trade, 'tp', None),
                "user_id": trade.user_id
            })
        
        return JSONResponse({
            "trades": trades_list,
            "total": total_trades,
            "skip": skip,
            "limit": limit
        })
        
    except Exception as e:
        logger.error(f"Error reading trades: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/api/stats")
async def get_stats(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_cookie)
):
    """Get trading statistics for the current user"""
    if not current_user:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    
    try:
        # Get all trades for this user
        trades = db.query(Trade).filter(Trade.user_id == current_user.id).all()
        
        # Calculate stats
        total_trades = len(trades)
        total_profit = sum(trade.profit for trade in trades) if trades else 0
        
        if total_trades > 0:
            win_count = sum(1 for trade in trades if trade.profit > 0)
            win_rate = (win_count / total_trades) * 100
        else:
            win_rate = 0
        
        avg_profit = total_profit / total_trades if total_trades > 0 else 0
        
        return JSONResponse({
            "total_trades": total_trades,
            "total_profit": total_profit,
            "win_rate": win_rate,
            "avg_profit": avg_profit,
            "last_sync_time": datetime.now().isoformat() if total_trades > 0 else None
        })
        
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post("/api/sync-mt5")
async def sync_mt5_api(
    request: Request,
    days: int = Query(30, description="Number of days to sync"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_cookie)
):
    """Sync trades from MT5 - API endpoint (identical to /sync but returns JSON)"""
    if not current_user:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    
    # Check if user has MT5 credentials
    if not current_user.mt5_server or not current_user.mt5_login or not current_user.mt5_password:
        return JSONResponse({"error": "MT5 credentials not configured"}, status_code=400)
    
    try:
        mt5 = MT5Client(
            server=current_user.mt5_server,
            login=current_user.mt5_login,
            password=current_user.mt5_password
        )
        trades = mt5.sync_trades(days=days)
        
        created = 0
        for trade in trades:
            crud.create_or_update_trade(db, trade, current_user.id)
            created += 1
        
        mt5.disconnect()
        
        # Get updated count
        total_in_db = db.query(Trade).filter(Trade.user_id == current_user.id).count()
        
        return JSONResponse({
            "success": True,
            "message": f"Successfully synced {created} trades from MT5",
            "synced_count": created,
            "total_in_db": total_in_db
        })
    except Exception as e:
        logger.error(f"Error syncing MT5: {e}")
        return JSONResponse({"error": str(e), "success": False}, status_code=400)

@app.get("/api/check-mt5-credentials")
async def check_mt5_credentials(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_cookie)
):
    """Check if MT5 credentials are set"""
    if not current_user:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    
    credentials_set = bool(
        current_user.mt5_server and 
        current_user.mt5_login and 
        current_user.mt5_password
    )
    
    return JSONResponse({
        "credentials_set": credentials_set,
        "has_server": bool(current_user.mt5_server),
        "has_login": bool(current_user.mt5_login),
        "has_password": bool(current_user.mt5_password)
    })

@app.post("/api/screenshot/{trade_id}")
async def upload_screenshot(
    trade_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_cookie)
):
    """Upload screenshot for a trade"""
    if not current_user:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    
    # Check if trade belongs to user
    trade = db.query(Trade).filter(Trade.id == trade_id, Trade.user_id == current_user.id).first()
    if not trade:
        return JSONResponse({"error": "Trade not found"}, status_code=404)
    
    try:
        # Save file
        content = await file.read()
        filename = save_screenshot(content, current_user.id, trade_id)
        
        # Update trade with screenshot path
        trade.screenshot = filename
        db.add(trade)
        db.commit()
        
        return JSONResponse({
            "success": True,
            "filename": filename,
            "trade_id": trade_id
        })
    except Exception as e:
        logger.error(f"Error uploading screenshot: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/api/toggle-theme")
async def toggle_theme(
    request: Request,
    current_user: User = Depends(get_current_user_from_cookie),
    db: Session = Depends(get_db)
):
    """Toggle theme between light and dark"""
    if not current_user:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    
    new_theme = "dark" if current_user.theme == "light" else "light"
    
    # Update in database
    if current_user.settings:
        current_user.settings.theme = new_theme
    else:
        user_settings = UserSettings(user_id=current_user.id, theme=new_theme)
        db.add(user_settings)
    
    db.commit()
    
    # Update cookie
    response = JSONResponse({"theme": new_theme})
    response.set_cookie(
        key="theme",
        value=new_theme,
        max_age=365*24*60*60,
        secure=False,
        samesite="lax"
    )
    
    return response

# ==================== AI-POWERED FEATURES ====================

@app.get("/weekly-report", response_class=HTMLResponse)
async def weekly_report_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_cookie)
):
    """Weekly report page"""
    if not current_user:
        return RedirectResponse(url="/login")
    
    # Get existing weekly reports
    weekly_reports = crud.get_weekly_reports(db, current_user.id, limit=5)
    
    # Check if user has badges
    badges = crud.get_user_badges(db, current_user.id)
    
    return templates.TemplateResponse("weekly-report.html", {
        "request": request,
        "user": current_user,
        "weekly_reports": weekly_reports,
        "badges": badges
    })

@app.post("/generate-weekly-report")
async def generate_weekly_report_endpoint(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_cookie)
):
    """Generate weekly report"""
    if not current_user:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    
    try:
        report = crud.generate_weekly_report(db, current_user.id)
        
        if report:
            return templates.TemplateResponse("weekly-report.html", {
                "request": request,
                "user": current_user,
                "weekly_reports": crud.get_weekly_reports(db, current_user.id, limit=5),
                "success": "Weekly report generated successfully!"
            })
        else:
            return templates.TemplateResponse("weekly-report.html", {
                "request": request,
                "user": current_user,
                "weekly_reports": crud.get_weekly_reports(db, current_user.id, limit=5),
                "error": "No trades found for the past week."
            })
    except Exception as e:
        logger.error(f"Error generating weekly report: {e}")
        return templates.TemplateResponse("weekly-report.html", {
            "request": request,
            "user": current_user,
            "weekly_reports": crud.get_weekly_reports(db, current_user.id, limit=5),
            "error": f"Error generating report: {str(e)}"
        })

@app.get("/badges", response_class=HTMLResponse)
async def badges_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_cookie)
):
    """Badges page"""
    if not current_user:
        return RedirectResponse(url="/login")
    
    badges = crud.get_user_badges(db, current_user.id)
    
    # Define badge descriptions
    badge_descriptions = {
        "best_trader": "Awarded for achieving >70% win rate with consistent profits",
        "consistency": "Awarded for maintaining profitable trades over multiple sessions",
        "risk_manager": "Awarded for excellent risk-reward ratio management",
        "high_profit": "Awarded for achieving exceptional profit levels",
        "disciplined": "Awarded for following trading rules consistently",
        "comeback_king": "Awarded for recovering from drawdown successfully"
    }
    
    return templates.TemplateResponse("badges.html", {
        "request": request,
        "user": current_user,
        "badges": badges,
        "badge_descriptions": badge_descriptions
    })

@app.get("/checklist", response_class=HTMLResponse)
async def checklist_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_cookie)
):
    """Trade checklist page"""
    if not current_user:
        return RedirectResponse(url="/login")
    
    # Get user's checklists
    user_checklists = crud.get_trade_checklists(db, current_user.id)
    
    # Get default checklists
    default_checklists = crud.get_default_checklists(db)
    
    return templates.TemplateResponse("checklist.html", {
        "request": request,
        "user": current_user,
        "user_checklists": user_checklists,
        "default_checklists": default_checklists
    })

@app.post("/checklist/create")
async def create_checklist(
    request: Request,
    name: str = Form(None),  # Make this optional
    title: str = Form(None),  # Add title field
    items_json: str = Form(None),  # Make this optional
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_cookie)
):
    """Create a new trade checklist - FIXED VERSION"""
    if not current_user:
        return RedirectResponse(url="/login")
    
    try:
        # Get the checklist name
        checklist_name = name or title or f"Checklist {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        
        # Get items
        items = []
        if items_json:
            try:
                parsed_items = json.loads(items_json)
                # Convert item IDs to strings
                for item in parsed_items:
                    if isinstance(item, dict):
                        item['id'] = str(item.get('id', len(items) + 1))
                        items.append(item)
            except json.JSONDecodeError:
                # If JSON parsing fails, treat as plain text
                pass
        
        # If no items from JSON, try to get form data
        if not items:
            form_data = await request.form()
            
            # Look for individual item fields
            for key, value in form_data.items():
                if key.startswith('item_') and value.strip():
                    items.append({
                        'id': str(len(items) + 1),
                        'text': value.strip(),
                        'checked': False,
                        'required': False
                    })
        
        # If still no items, check for items as newline-separated text
        if not items:
            form_data = await request.form()
            items_text = form_data.get('items', '')
            if items_text:
                item_list = [item.strip() for item in items_text.split('\n') if item.strip()]
                for i, text in enumerate(item_list):
                    items.append({
                        'id': str(i + 1),
                        'text': text,
                        'checked': False,
                        'required': False
                    })
        
        # If still no items, create default items
        if not items:
            items = [
                {'id': '1', 'text': 'Sample item 1', 'checked': False, 'required': True},
                {'id': '2', 'text': 'Sample item 2', 'checked': False, 'required': False}
            ]
        
        # Create checklist using the model directly to avoid schema validation issues
        items_json_str = json.dumps(items)
        
        db_checklist = TradeChecklist(
            user_id=current_user.id,
            name=checklist_name,
            items=items_json_str,
            created_at=datetime.utcnow()
        )
        
        db.add(db_checklist)
        db.commit()
        db.refresh(db_checklist)
        
        return templates.TemplateResponse("checklist.html", {
            "request": request,
            "user": current_user,
            "user_checklists": crud.get_trade_checklists(db, current_user.id),
            "default_checklists": crud.get_default_checklists(db),
            "success": f"Checklist '{checklist_name}' created successfully!"
        })
    except Exception as e:
        import traceback
        print(f"Error creating checklist: {e}")
        
        return templates.TemplateResponse("checklist.html", {
            "request": request,
            "user": current_user,
            "user_checklists": crud.get_trade_checklists(db, current_user.id),
            "default_checklists": crud.get_default_checklists(db),
            "error": f"Error creating checklist: {str(e)}"
        })

@app.get("/checklist/{checklist_id}/use")
async def use_checklist(
    checklist_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_cookie)
):
    """Use a default checklist by creating a user copy"""
    if not current_user:
        return RedirectResponse(url="/login")
    
    try:
        # Get the default checklist
        from app.models import TradeChecklist
        checklist = db.query(TradeChecklist).filter(
            TradeChecklist.id == checklist_id,
            TradeChecklist.is_default == True
        ).first()
        
        if not checklist:
            return RedirectResponse(url="/checklist")
        
        # Create a user copy
        checklist_create = schemas.TradeChecklistCreate(
            user_id=current_user.id,
            name=checklist.name + " (Copy)",
            items=checklist.items
        )
        
        crud.create_trade_checklist(db, checklist_create)
        
        return RedirectResponse(url="/checklist")
    except Exception as e:
        return RedirectResponse(url="/checklist")

@app.get("/news", response_class=HTMLResponse)
async def news_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_cookie)
):
    if not current_user:
        return RedirectResponse(url="/login")

    news_alerts = crud.get_news_alerts(db, current_user.id, limit=20)

    # Get symbol stats - these are SymbolStats objects, not dictionaries
    top_symbols_raw = crud.get_symbol_stats(db, current_user.id)
    
    # Extract just the symbol strings from SymbolStats objects
    top_symbols = []
    if top_symbols_raw:
        for stat in top_symbols_raw[:3]:  # Get top 3 symbols
            # SymbolStats objects have .symbol attribute, not ['symbol']
            if hasattr(stat, 'symbol'):
                top_symbols.append(stat.symbol)

    return templates.TemplateResponse(
        "news.html",
        {
            "request": request,
            "user": current_user,
            "news_alerts": news_alerts,
            "top_symbols": top_symbols,
        }
    )

@app.post("/news/fetch")
async def fetch_news(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_cookie)
):
    """Fetch latest news"""
    if not current_user:
        return RedirectResponse(url="/login")
    
    try:
        # Get user's top symbols - these are SymbolStats objects
        top_symbols = crud.get_symbol_stats(db, current_user.id)
        
        # Extract symbol strings from SymbolStats objects
        symbols = []
        if top_symbols:
            for stat in top_symbols[:3]:  # Get top 3 symbols
                if hasattr(stat, 'symbol') and stat.symbol:
                    symbols.append(stat.symbol)
        
        # Fetch and store news
        crud.fetch_and_store_news(db, current_user.id, symbols if symbols else None)
        
        return templates.TemplateResponse("news.html", {
            "request": request,
            "user": current_user,
            "news_alerts": crud.get_news_alerts(db, current_user.id, limit=20),
            "top_symbols": [stat.symbol for stat in top_symbols[:3]] if top_symbols else [],
            "success": "News updated successfully!"
        })
    except Exception as e:
        return templates.TemplateResponse("news.html", {
            "request": request,
            "user": current_user,
            "news_alerts": crud.get_news_alerts(db, current_user.id, limit=20),
            "top_symbols": [],
            "error": f"Error fetching news: {str(e)}"
        })

@app.post("/news/{news_id}/mark-read")
async def mark_news_read(
    news_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_cookie)
):
    """Mark news as read"""
    if not current_user:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    
    try:
        success = crud.mark_news_as_read(db, news_id, current_user.id)
        
        if success:
            return JSONResponse({"success": True})
        else:
            return JSONResponse({"error": "News not found"}, status_code=404)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/risk-reward", response_class=HTMLResponse)
async def risk_reward_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_cookie)
):
    """Risk-Reward analysis page"""
    if not current_user:
        return RedirectResponse(url="/login")
    
    # Get trades with SL/TP data
    trades = db.query(Trade).filter(
        Trade.user_id == current_user.id,
        Trade.sl.isnot(None),
        Trade.tp.isnot(None)
    ).order_by(Trade.time.desc()).limit(50).all()
    
    # Calculate risk-reward metrics
    risk_reward_data = []
    total_rrr = 0
    winning_rrr = 0
    losing_rrr = 0
    
    for trade in trades:
        if trade.sl and trade.tp:
            risk = abs(trade.entry_price - trade.sl)
            reward = abs(trade.tp - trade.entry_price)
            
            if risk > 0:
                rrr = reward / risk
                total_rrr += rrr
                
                if trade.profit > 0:
                    winning_rrr += rrr
                else:
                    losing_rrr += rrr
                
                risk_reward_data.append({
                    'ticket': trade.ticket,
                    'symbol': trade.symbol,
                    'type': trade.type,
                    'profit': trade.profit,
                    'risk': risk,
                    'reward': reward,
                    'rrr': rrr,
                    'win': trade.profit > 0,
                    'time': trade.time
                })
    
    avg_rrr = total_rrr / len(risk_reward_data) if risk_reward_data else 0
    avg_winning_rrr = winning_rrr / len([t for t in risk_reward_data if t['win']]) if any(t['win'] for t in risk_reward_data) else 0
    avg_losing_rrr = losing_rrr / len([t for t in risk_reward_data if not t['win']]) if any(not t['win'] for t in risk_reward_data) else 0
    
    # Calculate success rate by RRR
    success_by_rrr = {}
    for data in risk_reward_data:
        rrr_range = "1:1-1:1.5" if data['rrr'] < 1.5 else "1:1.5-1:2" if data['rrr'] < 2 else "1:2+"
        if rrr_range not in success_by_rrr:
            success_by_rrr[rrr_range] = {'total': 0, 'wins': 0}
        success_by_rrr[rrr_range]['total'] += 1
        if data['win']:
            success_by_rrr[rrr_range]['wins'] += 1
    
    return templates.TemplateResponse("risk-reward.html", {
        "request": request,
        "user": current_user,
        "risk_reward_data": risk_reward_data,
        "avg_rrr": avg_rrr,
        "avg_winning_rrr": avg_winning_rrr,
        "avg_losing_rrr": avg_losing_rrr,
        "success_by_rrr": success_by_rrr,
        "total_trades": len(risk_reward_data)
    })

# ==================== API ENDPOINTS FOR AI FEATURES ====================

@app.get("/api/weekly-report/generate")
async def api_generate_weekly_report(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_cookie)
):
    """API endpoint to generate weekly report"""
    if not current_user:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    
    try:
        report = crud.generate_weekly_report(db, current_user.id)
        
        if report:
            return JSONResponse({
                "success": True,
                "report_id": report.id,
                "message": "Weekly report generated successfully"
            })
        else:
            return JSONResponse({
                "success": False,
                "error": "No trades found for the past week"
            })
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)

@app.get("/api/badges")
async def api_get_badges(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_cookie)
):
    """Get user badges"""
    if not current_user:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    
    badges = crud.get_user_badges(db, current_user.id)
    
    return JSONResponse({
        "badges": [
            {
                "id": badge.id,
                "type": badge.badge_type,
                "description": badge.description,
                "awarded_date": badge.awarded_date.isoformat()
            }
            for badge in badges
        ]
    })

@app.get("/api/checklists")
async def api_get_checklists(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_cookie)
):
    """Get user checklists"""
    if not current_user:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    
    checklists = crud.get_trade_checklists(db, current_user.id)
    
    return JSONResponse({
        "checklists": [
            {
                "id": checklist.id,
                "name": checklist.name,
                "items": checklist.items,
                "created_at": checklist.created_at.isoformat()
            }
            for checklist in checklists
        ]
    })

@app.post("/checklist/create-debug")
async def create_checklist_debug(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_cookie)
):
    """Debug endpoint to see what's being sent"""
    if not current_user:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    
    try:
        # Get form data
        form_data = await request.form()
        
        return JSONResponse({
            "form_data": dict(form_data),
            "success": True
        })
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/api/news")
async def api_get_news(
    request: Request,
    unread_only: bool = False,
    limit: int = 10,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_cookie)
):
    """Get news alerts"""
    if not current_user:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    
    news_alerts = crud.get_news_alerts(db, current_user.id, limit=limit, unread_only=unread_only)
    
    return JSONResponse({
        "news": [
            {
                "id": news.id,
                "title": news.title,
                "summary": news.summary,
                "symbol": news.symbol,
                "impact": news.impact,
                "source": news.source,
                "published_at": news.published_at.isoformat(),
                "is_read": news.is_read
            }
            for news in news_alerts
        ]
    })

@app.get("/api/risk-reward-stats")
async def api_get_risk_reward_stats(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_cookie)
):
    """Get risk-reward statistics"""
    if not current_user:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    
    # Get trades with SL/TP
    trades = db.query(Trade).filter(
        Trade.user_id == current_user.id,
        Trade.sl.isnot(None),
        Trade.tp.isnot(None)
    ).all()
    
    if not trades:
        return JSONResponse({
            "message": "No trades with stop-loss and take-profit data"
        })
    
    # Calculate statistics
    rrr_values = []
    for trade in trades:
        risk = abs(trade.entry_price - trade.sl)
        reward = abs(trade.tp - trade.entry_price)
        if risk > 0:
            rrr_values.append({
                'rrr': reward / risk,
                'profit': trade.profit,
                'win': trade.profit > 0
            })
    
    if not rrr_values:
        return JSONResponse({
            "message": "No valid risk-reward ratios calculated"
        })
    
    # Calculate stats
    avg_rrr = sum(r['rrr'] for r in rrr_values) / len(rrr_values)
    winning_rrr = [r for r in rrr_values if r['win']]
    losing_rrr = [r for r in rrr_values if not r['win']]
    
    avg_winning_rrr = sum(r['rrr'] for r in winning_rrr) / len(winning_rrr) if winning_rrr else 0
    avg_losing_rrr = sum(r['rrr'] for r in losing_rrr) / len(losing_rrr) if losing_rrr else 0
    
    # Success rate by RRR range
    success_rate_by_range = {}
    for r in rrr_values:
        if r['rrr'] < 1:
            range_key = "Less than 1:1"
        elif r['rrr'] < 1.5:
            range_key = "1:1 to 1:1.5"
        elif r['rrr'] < 2:
            range_key = "1:1.5 to 1:2"
        else:
            range_key = "Greater than 1:2"
        
        if range_key not in success_rate_by_range:
            success_rate_by_range[range_key] = {'total': 0, 'wins': 0}
        
        success_rate_by_range[range_key]['total'] += 1
        if r['win']:
            success_rate_by_range[range_key]['wins'] += 1
    
    # Calculate win rates
    for key in success_rate_by_range:
        total = success_rate_by_range[key]['total']
        wins = success_rate_by_range[key]['wins']
        success_rate_by_range[key]['win_rate'] = (wins / total * 100) if total > 0 else 0
    
    return JSONResponse({
        'total_trades_analyzed': len(rrr_values),
        'avg_rrr': avg_rrr,
        'avg_winning_rrr': avg_winning_rrr,
        'avg_losing_rrr': avg_losing_rrr,
        'success_rate_by_range': success_rate_by_range,
        'recommended_rrr': max(1.5, avg_winning_rrr) if avg_winning_rrr > 0 else 1.5
    })

# ==================== HEALTH CHECK ====================

@app.get("/health")
async def health():
    """Health check endpoint"""
    return JSONResponse({
        "status": "ok", 
        "message": f"{settings.APP_NAME} is running", 
        "version": settings.VERSION
    })

# ==================== CREATE ADMIN USER ====================

@app.on_event("startup")
async def startup_event():
    """Create admin user on startup if not exists"""
    db_gen = get_db()
    db = next(db_gen)
    
    try:
        admin_user = crud.get_user_by_email(db, settings.ADMIN_EMAIL.strip())
        
        if not admin_user:
            # Create admin user with safe password handling
            admin_password = "Admin123!"  # Default fallback
            env_password = settings.ADMIN_PASSWORD.strip() if settings.ADMIN_PASSWORD else ""
            
            if env_password and len(env_password.encode('utf-8')) <= 72:
                admin_password = env_password
                print(f"Using provided admin password from .env")
            else:
                if env_password:
                    print(f"Warning: ADMIN_PASSWORD too long ({len(env_password.encode('utf-8'))} bytes). Using default password.")
                else:
                    print(f"Warning: No ADMIN_PASSWORD set in .env. Using default password.")
            
            # Ensure password is safe for bcrypt
            safe_password = admin_password.encode('utf-8')[:72].decode('utf-8', errors='ignore')
            
            # Hash the password
            hashed_password = auth.get_password_hash(safe_password)
            
            admin_user = User(
                email=settings.ADMIN_EMAIL.strip(),
                username="admin",
                full_name="Administrator",
                hashed_password=hashed_password,
                is_admin=True,
                is_verified=True,
                is_active=True
            )
            db.add(admin_user)
            db.commit()
            db.refresh(admin_user)
            
            # Create admin user settings
            user_settings = UserSettings(user_id=admin_user.id)
            db.add(user_settings)
            db.commit()
            
            print(f"✓ Admin user created successfully")
            print(f"  Email: {settings.ADMIN_EMAIL}")
            print(f"  Password: {admin_password[:8]}... (first 8 chars)")
        else:
            print(f"✓ Admin user already exists: {settings.ADMIN_EMAIL}")
        
        # Create default checklists
        crud.create_default_checklists(db)
        print("✓ Default checklists created")
    
    except Exception as e:
        print(f"✗ Error during startup: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        try:
            db_gen.close()
        except:
            pass



# Debug route to see registered routes
@app.get("/debug/routes")
async def debug_routes():
    routes = []
    for route in app.routes:
        if hasattr(route, "path"):
            routes.append({
                "path": route.path,
                "name": route.name,
                "methods": list(route.methods) if hasattr(route, 'methods') else []
            })
    return {"routes": sorted(routes, key=lambda x: x["path"])}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)