# app/schemas.py - FINAL FIXED VERSION
from pydantic import BaseModel
from datetime import datetime
from typing import Optional

# Trade schemas
class TradeBase(BaseModel):
    ticket: int
    position_id: int
    time: datetime
    type: str
    symbol: str
    volume: float
    price: float
    profit: float

class TradeCreate(TradeBase):
    sl: Optional[float] = 0
    tp: Optional[float] = 0
    time_close: Optional[datetime] = None
    price_close: Optional[float] = None
    commission: float = 0
    swap: float = 0
    comment: Optional[str] = ""
    # NO win field here - it's calculated by crud.py
    
    class Config:
        from_attributes = True

class Trade(TradeBase):
    id: int
    sl: Optional[float] = 0
    tp: Optional[float] = 0
    time_close: Optional[datetime] = None
    price_close: Optional[float] = None
    commission: float = 0
    swap: float = 0
    comment: Optional[str] = ""
    duration_minutes: Optional[int] = None
    pips: Optional[float] = None
    win: Optional[bool] = None
    synced_at: datetime
    
    class Config:
        from_attributes = True

# User schemas
class UserBase(BaseModel):
    username: str
    email: str

class UserCreate(UserBase):
    password: str

class User(UserBase):
    id: int
    is_active: bool
    
    class Config:
        from_attributes = True

# Token schemas
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

# Stats schemas
class StatsResponse(BaseModel):
    total_trades: int
    total_profit: float
    win_rate: float
    avg_profit: float
    best_symbol: Optional[str] = None
    worst_symbol: Optional[str] = None

# Calendar schemas
class DayStats(BaseModel):
    date: str
    trades_count: int
    profit: float
    win_rate: float

class MonthCalendar(BaseModel):
    year: int
    month: int
    days: list[DayStats]