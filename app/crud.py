# app/crud.py - COMPLETE UPDATED VERSION WITH ARGON2
from sqlalchemy.orm import Session
from sqlalchemy import and_, func, extract, case, desc
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import json

from . import models, schemas, auth, ai_service
from .utils import send_email, generate_verification_email, generate_password_reset_email

# User CRUD
def get_user(db: Session, user_id: int):
    return db.query(models.User).filter(models.User.id == user_id).first()

def get_user_by_email(db: Session, email: str):
    return db.query(models.User).filter(models.User.email == email).first()

def get_user_by_username(db: Session, username: str):
    return db.query(models.User).filter(models.User.username == username).first()

def create_user(db: Session, user: schemas.UserCreate):
    """Create new user with Argon2 password hashing"""
    hashed_password = auth.get_password_hash(user.password)
    db_user = models.User(
        email=user.email,
        username=user.username,
        full_name=user.full_name,
        hashed_password=hashed_password,
        is_admin=False,
        is_verified=False
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    # Create user settings
    user_settings = models.UserSettings(user_id=db_user.id)
    db.add(user_settings)
    db.commit()
    
    return db_user

def get_user_settings(db: Session, user_id: int):
    """Get user settings or create default if not exists"""
    user_settings = db.query(models.UserSettings).filter(models.UserSettings.user_id == user_id).first()
    if not user_settings:
        # Create default settings
        user_settings = models.UserSettings(
            user_id=user_id,
            chart_theme="light",
            chart_type="candlestick",
            show_grid=True,
            show_volume=False,
            email_notifications=True,
            trade_alerts=True,
            report_frequency="weekly"
        )
        db.add(user_settings)
        db.commit()
        db.refresh(user_settings)
    return user_settings

def update_user(db: Session, user_id: int, user_update: schemas.UserUpdate) -> models.User:
    """Update user information - FIXED VERSION"""
    db_user = db.query(models.User).filter(models.User.id == user_id).first()
    if not db_user:
        raise ValueError("User not found")
    
    # Update basic fields if provided
    update_dict = user_update.dict(exclude_unset=True)
    
    # Handle password change separately
    if 'password' in update_dict and update_dict['password']:
        if 'current_password' not in update_dict:
            raise ValueError("Current password is required to change password")
        
        # Verify current password
        if not auth.verify_password(update_dict['current_password'], db_user.hashed_password):
            raise ValueError("Current password is incorrect")
        
        # Update to new password
        db_user.hashed_password = auth.get_password_hash(update_dict['password'])
        # Remove password fields from update_dict so we don't try to set them as attributes
        update_dict.pop('password')
        update_dict.pop('current_password')
    
    # Update other fields (excluding internal fields)
    excluded_fields = ['id', 'created_at', 'updated_at', 'hashed_password']
    for field, value in update_dict.items():
        if hasattr(db_user, field) and field not in excluded_fields:
            setattr(db_user, field, value)
    
    db.commit()
    db.refresh(db_user)
    return db_user

def update_user_mt5_credentials(db: Session, user_id: int, credentials: schemas.UserUpdate):
    """Update MT5 credentials - using UserUpdate schema instead of UserMT5Credentials"""
    db_user = get_user(db, user_id)
    if not db_user:
        return None
    
    if credentials.mt5_server is not None:
        db_user.mt5_server = credentials.mt5_server
    if credentials.mt5_login is not None:
        db_user.mt5_login = credentials.mt5_login
    if credentials.mt5_password is not None:
        db_user.mt5_password = credentials.mt5_password
    
    db.commit()
    db.refresh(db_user)
    return db_user

def update_user_settings(db: Session, user_id: int, settings_update: schemas.UserSettingsUpdate):
    """Update user settings"""
    user_settings = get_user_settings(db, user_id)
    
    # Update fields
    for field, value in settings_update.dict(exclude_unset=True).items():
        setattr(user_settings, field, value)
    
    db.commit()
    db.refresh(user_settings)
    return user_settings

def verify_user(db: Session, email: str):
    """Mark user as verified"""
    db_user = get_user_by_email(db, email)
    if db_user:
        db_user.is_verified = True
        db.commit()
        db.refresh(db_user)
    return db_user

def reset_password(db: Session, email: str, new_password: str):
    """Reset user password with Argon2"""
    db_user = get_user_by_email(db, email)
    if db_user:
        db_user.hashed_password = auth.get_password_hash(new_password)
        db.commit()
        db.refresh(db_user)
    return db_user

def get_users(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.User).offset(skip).limit(limit).all()

def count_users(db: Session):
    return db.query(models.User).count()

# Trade CRUD
def get_trades(db: Session, user_id: int, skip: int = 0, limit: int = 100, 
               symbol: Optional[str] = None, start_date: Optional[datetime] = None,
               end_date: Optional[datetime] = None, days: Optional[int] = None):
    query = db.query(models.Trade).filter(models.Trade.user_id == user_id)
    
    if symbol:
        query = query.filter(models.Trade.symbol == symbol)
    if start_date:
        query = query.filter(models.Trade.time >= start_date)
    if end_date:
        query = query.filter(models.Trade.time <= end_date)
    if days:
        start_date_filter = datetime.utcnow() - timedelta(days=days)
        query = query.filter(models.Trade.time >= start_date_filter)
    
    return query.order_by(models.Trade.time.desc()).offset(skip).limit(limit).all()

def get_trade(db: Session, trade_id: int, user_id: int):
    return db.query(models.Trade).filter(
        models.Trade.id == trade_id,
        models.Trade.user_id == user_id
    ).first()

def create_or_update_trade(db: Session, trade: schemas.TradeCreate, user_id: int):
    db_trade = db.query(models.Trade).filter(
        models.Trade.ticket == trade.ticket,
        models.Trade.user_id == user_id
    ).first()
    
    if db_trade:
        # Update existing trade
        for key, value in trade.dict().items():
            setattr(db_trade, key, value)
    else:
        # Create new trade
        db_trade = models.Trade(**trade.dict(), user_id=user_id)
        db.add(db_trade)
    
    db.commit()
    db.refresh(db_trade)
    return db_trade

def update_trade(db: Session, trade_id: int, user_id: int, trade_update: schemas.TradeUpdate):
    db_trade = get_trade(db, trade_id, user_id)
    if not db_trade:
        return None
    
    update_data = trade_update.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_trade, key, value)
    
    db.commit()
    db.refresh(db_trade)
    return db_trade

def delete_trade(db: Session, trade_id: int, user_id: int):
    db_trade = get_trade(db, trade_id, user_id)
    if db_trade:
        db.delete(db_trade)
        db.commit()
        return True
    return False

def get_trade_stats(db: Session, user_id: int, 
                    start_date: Optional[datetime] = None, 
                    end_date: Optional[datetime] = None):
    query = db.query(models.Trade).filter(models.Trade.user_id == user_id)
    
    if start_date:
        query = query.filter(models.Trade.time >= start_date)
    if end_date:
        query = query.filter(models.Trade.time <= end_date)
    
    trades = query.all()
    
    if not trades:
        return schemas.TradeStats()
    
    total_trades = len(trades)
    winning_trades = sum(1 for t in trades if t.profit > 0)
    losing_trades = total_trades - winning_trades
    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
    total_profit = sum(t.profit for t in trades)
    avg_profit = total_profit / total_trades if total_trades > 0 else 0
    
    profits = [t.profit for t in trades if t.profit > 0]
    losses = [t.profit for t in trades if t.profit < 0]
    
    max_profit = max(profits) if profits else 0
    max_loss = min(losses) if losses else 0
    
    total_wins = sum(profits)
    total_losses = abs(sum(losses))
    profit_factor = total_wins / total_losses if total_losses > 0 else 0
    
    return schemas.TradeStats(
        total_trades=total_trades,
        winning_trades=winning_trades,
        losing_trades=losing_trades,
        win_rate=win_rate,
        total_profit=total_profit,
        avg_profit=avg_profit,
        max_profit=max_profit,
        max_loss=max_loss,
        profit_factor=profit_factor
    )







def get_symbol_stats(db: Session, user_id: int):
    """Get trading statistics grouped by symbol for a user"""
    # Create win_case using the correct SQLAlchemy case syntax
    win_case = case(
        (models.Trade.profit > 0, 1),
        else_=0
    )
    
    result = db.query(
        models.Trade.symbol,
        func.count(models.Trade.id).label('total_trades'),
        func.avg(models.Trade.profit).label('avg_profit'),
        func.sum(models.Trade.profit).label('total_profit'),
        func.sum(win_case).label('win_count'),  # CHANGED THIS LINE
        (func.sum(win_case) / func.count(models.Trade.id) * 100).label('win_rate')
    ).filter(
        models.Trade.user_id == user_id
    ).group_by(
        models.Trade.symbol
    ).order_by(
        func.count(models.Trade.id).desc()
    ).all()
    
    return [
        schemas.SymbolStats(
            symbol=r.symbol,
            total_trades=r.total_trades,
            win_count=r.win_count,  # CHANGED THIS LINE
            win_rate=float(r.win_rate or 0),
            total_profit=float(r.total_profit or 0),
            avg_profit=float(r.avg_profit or 0)
        )
        for r in result
    ]









def get_hourly_stats(db: Session, user_id: int):
    """Get trading statistics grouped by hour of day"""
    # Create win_case using the correct SQLAlchemy case syntax
    win_case = case(
        (models.Trade.profit > 0, 1),
        else_=0
    )
    
    result = db.query(
        extract('hour', models.Trade.time).label('hour'),
        func.count(models.Trade.id).label('total_trades'),
        func.sum(models.Trade.profit).label('total_profit'),
        # Use the win_case variable in the calculation
        (func.sum(win_case) / func.count(models.Trade.id) * 100).label('win_rate')
    ).filter(
        models.Trade.user_id == user_id
    ).group_by(
        extract('hour', models.Trade.time)
    ).order_by(
        extract('hour', models.Trade.time)
    ).all()
    
    return [
        schemas.HourlyStats(
            hour=int(r.hour),
            total_trades=r.total_trades,
            win_rate=float(r.win_rate or 0),
            total_profit=float(r.total_profit or 0)
        )
        for r in result
    ]

# Additional utility functions
def get_user_trade_count(db: Session, user_id: int):
    """Get total number of trades for a user"""
    return db.query(models.Trade).filter(models.Trade.user_id == user_id).count()

def get_recent_trades(db: Session, user_id: int, limit: int = 10):
    """Get recent trades for a user"""
    return db.query(models.Trade)\
        .filter(models.Trade.user_id == user_id)\
        .order_by(models.Trade.time.desc())\
        .limit(limit)\
        .all()

def get_daily_stats(db: Session, user_id: int, date: datetime):
    """Get stats for a specific day"""
    start_of_day = datetime(date.year, date.month, date.day)
    end_of_day = start_of_day + timedelta(days=1)
    
    trades = db.query(models.Trade)\
        .filter(
            models.Trade.user_id == user_id,
            models.Trade.time >= start_of_day,
            models.Trade.time < end_of_day
        )\
        .all()
    
    if not trades:
        return {
            "date": date.date(),
            "total_trades": 0,
            "total_profit": 0,
            "winning_trades": 0,
            "losing_trades": 0
        }
    
    total_profit = sum(t.profit for t in trades)
    winning_trades = sum(1 for t in trades if t.profit > 0)
    
    return {
        "date": date.date(),
        "total_trades": len(trades),
        "total_profit": total_profit,
        "winning_trades": winning_trades,
        "losing_trades": len(trades) - winning_trades
    }

# Badge CRUD operations
def get_user_badges(db: Session, user_id: int) -> List[models.UserBadge]:
    return db.query(models.UserBadge).filter(
        models.UserBadge.user_id == user_id
    ).order_by(models.UserBadge.awarded_date.desc()).all()

def create_user_badge(db: Session, badge: schemas.BadgeCreate) -> models.UserBadge:
    db_badge = models.UserBadge(**badge.dict())
    db.add(db_badge)
    db.commit()
    db.refresh(db_badge)
    return db_badge

def check_and_award_badges(db: Session, user_id: int) -> List[models.UserBadge]:
    """Check if user qualifies for any badges and award them"""
    # Get user's recent trades
    recent_trades = get_trades(db, user_id, days=30)
    
    # Use AI service to check for badges
    badge_awarder = ai_service.badge_awarder
    qualified_badges = badge_awarder.check_for_badges(db, user_id, recent_trades)
    
    awarded_badges = []
    existing_badges = {b.badge_type for b in get_user_badges(db, user_id)}
    
    for badge_info in qualified_badges:
        if badge_info['badge_type'] not in existing_badges:
            badge_create = schemas.BadgeCreate(
                user_id=user_id,
                badge_type=badge_info['badge_type'],
                description=badge_info['description']
            )
            awarded_badge = create_user_badge(db, badge_create)
            awarded_badges.append(awarded_badge)
    
    return awarded_badges

# Weekly Report CRUD operations
def get_weekly_reports(db: Session, user_id: int, limit: int = 10) -> List[models.WeeklyReport]:
    return db.query(models.WeeklyReport).filter(
        models.WeeklyReport.user_id == user_id
    ).order_by(desc(models.WeeklyReport.week_end)).limit(limit).all()

def get_weekly_report_by_date(db: Session, user_id: int, week_start: datetime) -> Optional[models.WeeklyReport]:
    return db.query(models.WeeklyReport).filter(
        and_(
            models.WeeklyReport.user_id == user_id,
            models.WeeklyReport.week_start == week_start
        )
    ).first()

def create_weekly_report(db: Session, report: schemas.WeeklyReportCreate) -> models.WeeklyReport:
    db_report = models.WeeklyReport(**report.dict())
    db.add(db_report)
    db.commit()
    db.refresh(db_report)
    return db_report

def generate_weekly_report(db: Session, user_id: int) -> Optional[models.WeeklyReport]:
    """Generate AI-powered weekly report"""
    # Get date range for last week
    today = datetime.utcnow()
    week_end = today.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = week_end - timedelta(days=7)
    
    # Check if report already exists
    existing_report = get_weekly_report_by_date(db, user_id, week_start)
    if existing_report:
        return existing_report
    
    # Get trades for the week
    trades = get_trades(db, user_id, start_date=week_start, end_date=week_end)
    
    if not trades:
        return None
    
    # Calculate basic statistics
    total_trades = len(trades)
    winning_trades = [t for t in trades if t.profit > 0]
    win_rate = len(winning_trades) / total_trades * 100 if total_trades > 0 else 0
    total_profit = sum(t.profit for t in trades)
    
    # Calculate average risk-reward ratio
    rrr_values = []
    for trade in trades:
        if trade.sl and trade.tp:
            risk = abs(trade.entry_price - trade.sl)
            reward = abs(trade.tp - trade.entry_price)
            if risk > 0:
                rrr_values.append(reward / risk)
    
    avg_rrr = sum(rrr_values) / len(rrr_values) if rrr_values else 0
    
    # Get best and worst trades
    best_trade = max(trades, key=lambda x: x.profit) if trades else None
    worst_trade = min(trades, key=lambda x: x.profit) if trades else None
    
    # Use AI to analyze performance
    ai_analyzer = ai_service.ai_analyzer
    
    # Convert trades to dict for AI analysis
    trades_dict = [{
        'symbol': t.symbol,
        'type': t.type,
        'profit': t.profit,
        'win': t.profit > 0,
        'volume': t.volume,
        'time': t.time,
        'sl': t.sl,
        'tp': t.tp
    } for t in trades]
    
    analysis = ai_analyzer.analyze_weekly_performance(trades_dict)
    
    # Create report
    report_data = {
        'user_id': user_id,
        'week_start': week_start,
        'week_end': week_end,
        'total_trades': total_trades,
        'win_rate': win_rate,
        'total_profit': total_profit,
        'avg_rrr': avg_rrr,
        'performance_score': analysis.get('performance_score', 0),
        'summary': analysis.get('summary', ''),
        'best_trade': {
            'ticket': best_trade.ticket if best_trade else None,
            'symbol': best_trade.symbol if best_trade else None,
            'profit': best_trade.profit if best_trade else None
        } if best_trade else None,
        'worst_trade': {
            'ticket': worst_trade.ticket if worst_trade else None,
            'symbol': worst_trade.symbol if worst_trade else None,
            'profit': worst_trade.profit if worst_trade else None
        } if worst_trade else None,
        'recommendations': analysis.get('recommendations', []),
        'patterns_identified': analysis.get('patterns', []),
        'sentiment_analysis': analysis.get('sentiment', ''),
        'next_week_outlook': analysis.get('outlook', '')
    }
    
    report_create = schemas.WeeklyReportCreate(**report_data)
    report = create_weekly_report(db, report_create)
    
    # Check for badges after generating report
    check_and_award_badges(db, user_id)
    
    return report

# Trade Checklist CRUD operations
def get_trade_checklists(db: Session, user_id: int) -> List[models.TradeChecklist]:
    return db.query(models.TradeChecklist).filter(
        models.TradeChecklist.user_id == user_id
    ).order_by(models.TradeChecklist.created_at.desc()).all()

def get_default_checklists(db: Session) -> List[models.TradeChecklist]:
    return db.query(models.TradeChecklist).filter(
        models.TradeChecklist.is_default == True
    ).all()

def create_trade_checklist(db: Session, checklist: schemas.TradeChecklistCreate) -> models.TradeChecklist:
    db_checklist = models.TradeChecklist(**checklist.dict())
    db.add(db_checklist)
    db.commit()
    db.refresh(db_checklist)
    return db_checklist

def create_default_checklists(db: Session):
    """Create default trade checklists"""
    default_checklists = [
        {
            'name': 'Pre-Trade Checklist',
            'items': [
                {'id': '1', 'text': 'Check economic calendar for news', 'required': True},
                {'id': '2', 'text': 'Analyze support/resistance levels', 'required': True},
                {'id': '3', 'text': 'Set stop-loss and take-profit levels', 'required': True},
                {'id': '4', 'text': 'Calculate position size (risk < 2% of account)', 'required': True},
                {'id': '5', 'text': 'Check for major trend direction', 'required': False},
                {'id': '6', 'text': 'Verify entry signal confirmation', 'required': True}
            ],
            'is_default': True
        },
        {
            'name': 'Risk Management Checklist',
            'items': [
                {'id': '1', 'text': 'Maximum daily loss limit set', 'required': True},
                {'id': '2', 'text': 'Maximum trade risk per trade (1-2%)', 'required': True},
                {'id': '3', 'text': 'Risk-Reward ratio > 1:1.5', 'required': True},
                {'id': '4', 'text': 'No revenge trading', 'required': True},
                {'id': '5', 'text': 'Account for spreads and commissions', 'required': False}
            ],
            'is_default': True
        }
    ]
    
    for checklist_data in default_checklists:
        # Check if already exists
        existing = db.query(models.TradeChecklist).filter(
            and_(
                models.TradeChecklist.name == checklist_data['name'],
                models.TradeChecklist.is_default == True
            )
        ).first()
        
        if not existing:
            checklist = models.TradeChecklist(
                name=checklist_data['name'],
                items=checklist_data['items'],
                is_default=True,
                user_id=None  # Default checklists don't have user_id
            )
            db.add(checklist)
    
    db.commit()

# News Alerts CRUD operations
def get_news_alerts(db: Session, user_id: int, limit: int = 20, unread_only: bool = False) -> List[models.NewsAlert]:
    query = db.query(models.NewsAlert).filter(
        models.NewsAlert.user_id == user_id
    )
    
    if unread_only:
        query = query.filter(models.NewsAlert.is_read == False)
    
    return query.order_by(desc(models.NewsAlert.published_at)).limit(limit).all()

def create_news_alert(db: Session, news: schemas.NewsAlertCreate) -> models.NewsAlert:
    db_news = models.NewsAlert(**news.dict())
    db.add(db_news)
    db.commit()
    db.refresh(db_news)
    return db_news

def mark_news_as_read(db: Session, news_id: int, user_id: int) -> bool:
    news = db.query(models.NewsAlert).filter(
        and_(
            models.NewsAlert.id == news_id,
            models.NewsAlert.user_id == user_id
        )
    ).first()
    
    if news:
        news.is_read = True
        db.commit()
        return True
    
    return False

def fetch_and_store_news(db: Session, user_id: int, symbols: List[str] = None):
    """Fetch news from API and store for user"""
    # FIX: Use the existing instance instead of creating new one
    news_aggregator = ai_service.news_aggregator
    # FIX: Use get_market_news() which actually exists
    news_items = news_aggregator.get_market_news()
    
    for item in news_items:
        # Check if news already exists for user
        existing = db.query(models.NewsAlert).filter(
            and_(
                models.NewsAlert.user_id == user_id,
                models.NewsAlert.title == item['title'][:200],  # Truncate if too long
                models.NewsAlert.published_at == item['published_at']
            )
        ).first()
        
        if not existing:
            news_create = schemas.NewsAlertCreate(
                user_id=user_id,
                symbol=item.get('symbol'),
                title=item['title'][:200],
                summary=item.get('summary'),
                source=item.get('source'),
                published_at=item['published_at']
            )
            create_news_alert(db, news_create)
    
    db.commit()