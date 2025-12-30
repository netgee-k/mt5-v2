# app/crud.py - COMPLETE FIXED VERSION
from sqlalchemy.orm import Session
from sqlalchemy import func, case
from datetime import datetime, timedelta
from typing import Optional

from . import models, schemas
from .auth import get_password_hash

# ==================== USER CRUD ====================

def get_user(db: Session, username: str):
    return db.query(models.User).filter(models.User.username == username).first()

def create_user(db: Session, user: schemas.UserCreate):
    hashed_password = get_password_hash(user.password)
    db_user = models.User(
        username=user.username,
        email=user.email,
        hashed_password=hashed_password
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

# ==================== TRADE CRUD ====================

def get_trade(db: Session, ticket: int):
    return db.query(models.Trade).filter(models.Trade.ticket == ticket).first()

def get_trades(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.Trade).order_by(models.Trade.time.desc()).offset(skip).limit(limit).all()

def create_trade(db: Session, trade: schemas.TradeCreate):
    """Create a new trade with calculated fields"""
    # Calculate additional fields
    duration_minutes = None
    pips = None
    win = trade.profit > 0 if trade.profit is not None else None

    if trade.time_close and trade.time:
        duration = trade.time_close - trade.time
        duration_minutes = int(duration.total_seconds() / 60)

    if trade.price_close and trade.price:
        if trade.type == 'BUY':
            pips = (trade.price_close - trade.price) * 10000
        else:
            pips = (trade.price - trade.price_close) * 10000

    db_trade = models.Trade(
        **trade.dict(),
        duration_minutes=duration_minutes,
        pips=pips,
        win=win,
        synced_at=datetime.now()
    )
    db.add(db_trade)
    db.commit()
    db.refresh(db_trade)
    return db_trade

def create_or_update_trade(db: Session, trade: schemas.TradeCreate):
    """Create or update a trade with recalculated fields"""
    existing_trade = get_trade(db, trade.ticket)
    
    if existing_trade:
        # Update existing trade - recalculate fields
        for key, value in trade.dict().items():
            setattr(existing_trade, key, value)
        
        # Recalculate derived fields
        existing_trade.win = trade.profit > 0 if trade.profit is not None else None
        
        if trade.time_close and trade.time:
            duration = trade.time_close - trade.time
            existing_trade.duration_minutes = int(duration.total_seconds() / 60)
        else:
            existing_trade.duration_minutes = None
        
        if trade.price_close and trade.price:
            if trade.type == 'BUY':
                existing_trade.pips = (trade.price_close - trade.price) * 10000
            else:
                existing_trade.pips = (trade.price - trade.price_close) * 10000
        else:
            existing_trade.pips = None
        
        existing_trade.synced_at = datetime.now()
        
        db.commit()
        db.refresh(existing_trade)
        return existing_trade
    else:
        # Create new trade
        return create_trade(db, trade)

# ==================== STATISTICS ====================

def get_trade_stats(db: Session, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None):
    query = db.query(models.Trade)

    if start_date:
        query = query.filter(models.Trade.time >= start_date)
    if end_date:
        query = query.filter(models.Trade.time <= end_date)

    total_trades = query.count()
    if total_trades == 0:
        return {
            'total_trades': 0,
            'total_profit': 0,
            'win_rate': 0,
            'avg_profit': 0,
            'win_count': 0,
            'loss_count': 0
        }

    result = query.with_entities(
        func.count(models.Trade.id).label('total_trades'),
        func.sum(models.Trade.profit).label('total_profit'),
        func.avg(models.Trade.profit).label('avg_profit'),
        func.sum(case((models.Trade.win == True, 1), else_=0)).label('win_count'),
        func.sum(case((models.Trade.win == False, 1), else_=0)).label('loss_count')
    ).first()

    win_rate = (result.win_count / total_trades * 100) if total_trades > 0 else 0

    return {
        'total_trades': total_trades,
        'total_profit': result.total_profit or 0,
        'avg_profit': result.avg_profit or 0,
        'win_rate': win_rate,
        'win_count': result.win_count or 0,
        'loss_count': result.loss_count or 0
    }

def get_symbol_stats(db: Session):
    return db.query(
        models.Trade.symbol,
        func.count(models.Trade.id).label('total_trades'),
        func.sum(models.Trade.profit).label('total_profit'),
        func.avg(models.Trade.profit).label('avg_profit'),
        func.sum(case((models.Trade.win == True, 1), else_=0)).label('win_count')
    ).group_by(models.Trade.symbol).all()

def get_daily_stats(db: Session, date: datetime):
    start_of_day = datetime(date.year, date.month, date.day)
    end_of_day = start_of_day + timedelta(days=1)
    return get_trade_stats(db, start_of_day, end_of_day)

def get_hourly_stats(db: Session):
    stats = []
    for hour in range(24):
        query = db.query(models.Trade).filter(
            func.extract('hour', models.Trade.time) == hour
        )

        total_trades = query.count()
        if total_trades > 0:
            result = query.with_entities(
                func.count(models.Trade.id).label('total_trades'),
                func.sum(models.Trade.profit).label('total_profit'),
                func.sum(case((models.Trade.win == True, 1), else_=0)).label('win_count')
            ).first()

            win_rate = (result.win_count / total_trades * 100) if total_trades > 0 else 0

            stats.append({
                'hour': hour,
                'total_trades': total_trades,
                'total_profit': result.total_profit or 0,
                'win_rate': win_rate,
                'win_count': result.win_count or 0
            })

    return stats