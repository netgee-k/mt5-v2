
# app/main.py - COMPLETE WORKING VERSION (NO AUTH)
from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Optional
import calendar as cal

from . import crud, schemas
from .database import get_db, engine, Base
from .mt5_client import MT5Client
from .models import Trade

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="MT5 Trading Journal", version="1.0.0")

# Mount static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Templates
templates = Jinja2Templates(directory="app/templates")

# ==================== PUBLIC ROUTES (NO AUTH REQUIRED) ====================

@app.get("/", response_class=HTMLResponse)
async def home_page(request: Request, db: Session = Depends(get_db)):
    """Home page - redirects directly to dashboard"""
    return RedirectResponse(url="/dashboard")

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(
    request: Request, 
    db: Session = Depends(get_db)
):
    """Dashboard page"""
    stats = crud.get_trade_stats(db)
    recent_trades = crud.get_trades(db, limit=10)
    symbol_stats = crud.get_symbol_stats(db)
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
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
    db: Session = Depends(get_db)
):
    """Calendar page"""
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
        start_date=first_day,
        end_date=last_day
    )
    
    return templates.TemplateResponse("calendar.html", {
        "request": request,
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
    db: Session = Depends(get_db)
):
    """Statistics page"""
    today = datetime.now().date()
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)
    
    overall_stats = crud.get_trade_stats(db)
    weekly_stats = crud.get_trade_stats(db, start_date=week_ago)
    monthly_stats = crud.get_trade_stats(db, start_date=month_ago)
    symbol_stats = crud.get_symbol_stats(db)
    hourly_stats = crud.get_hourly_stats(db)
    
    return templates.TemplateResponse("stats.html", {
        "request": request,
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
    db: Session = Depends(get_db)
):
    """Trades page"""
    query = db.query(Trade).order_by(Trade.time.desc())
    
    if symbol:
        query = query.filter(Trade.symbol == symbol)
    
    total_trades = query.count()
    trades = query.offset(skip).limit(limit).all()
    
    symbols = db.query(Trade.symbol).distinct().all()
    
    return templates.TemplateResponse("trades.html", {
        "request": request,
        "trades": trades,
        "total_trades": total_trades,
        "symbols": [s[0] for s in symbols],
        "current_symbol": symbol,
        "skip": skip,
        "limit": limit,
    })

@app.get("/sync", response_class=HTMLResponse)
async def sync_page(request: Request):
    """Sync page for manual MT5 sync"""
    return templates.TemplateResponse("sync.html", {"request": request})

@app.post("/sync")
async def sync_post(
    request: Request,
    days: int = Form(30),
    db: Session = Depends(get_db)
):
    """Handle manual sync from form"""
    try:
        mt5 = MT5Client()
        trades = mt5.sync_trades(days=days)
        
        created = 0
        for trade in trades:
            crud.create_or_update_trade(db, trade)
            created += 1
        
        mt5.disconnect()
        
        return templates.TemplateResponse("sync.html", {
            "request": request,
            "message": f"Successfully synced {created} trades from MT5"
        })
    except Exception as e:
        return templates.TemplateResponse("sync.html", {
            "request": request,
            "error": f"Sync failed: {str(e)}"
        })

# ==================== API ENDPOINTS ====================

@app.get("/api/trades", response_model=list[schemas.Trade])
async def read_trades(
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db)
):
    """Get trades (API)"""
    trades = crud.get_trades(db, skip=skip, limit=limit)
    return trades

@app.get("/api/stats")
async def read_stats(db: Session = Depends(get_db)):
    """Get statistics (API)"""
    return crud.get_trade_stats(db)

@app.post("/api/sync-mt5")
async def sync_mt5(
    days: int = 30, 
    db: Session = Depends(get_db)
):
    """Sync with MT5 (API)"""
    try:
        mt5 = MT5Client()
        trades = mt5.sync_trades(days=days)
        
        created = 0
        for trade in trades:
            crud.create_or_update_trade(db, trade)
            created += 1
        
        mt5.disconnect()
        
        return {
            "success": True,
            "message": f"Synced {created} trades",
            "total_in_db": db.query(Trade).count()
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

# ==================== HEALTH CHECK ====================

@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "ok", "message": "MT5 Trading Journal is running"}

# ==================== SIMPLIFIED TEMPLATE CONTEXT ====================

# You'll also need to update your templates to remove user references
# Example for dashboard.html template:
"""
Remove lines like:
{% if user %}
  Welcome, {{ user.username }}
{% endif %}

Change to simply display content without user context
"""

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)