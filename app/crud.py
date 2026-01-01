# app/crud.py - COMPLETE UPDATED VERSION WITH ARGON2
from sqlalchemy.orm import Session
from sqlalchemy import and_, func, extract, case
from datetime import datetime, timedelta
from typing import Optional, List
from . import models, schemas, auth
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
               end_date: Optional[datetime] = None):
    query = db.query(models.Trade).filter(models.Trade.user_id == user_id)
    
    if symbol:
        query = query.filter(models.Trade.symbol == symbol)
    if start_date:
        query = query.filter(models.Trade.time >= start_date)
    if end_date:
        query = query.filter(models.Trade.time <= end_date)
    
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
        # Use the win_case variable in the calculation
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