# app/schemas.py - COMPLETE UPDATED VERSION
from pydantic import BaseModel, Field, EmailStr, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

# User Schemas
class UserBase(BaseModel):
    email: EmailStr
    username: str
    full_name: Optional[str] = None

class UserCreate(UserBase):
    password: str
    
    @validator('password')
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        return v

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    username: Optional[str] = None
    full_name: Optional[str] = None
    current_password: Optional[str] = None
    password: Optional[str] = None
    mt5_server: Optional[str] = None
    mt5_login: Optional[int] = None
    mt5_password: Optional[str] = None
    theme: Optional[str] = None
    timezone: Optional[str] = None

class User(UserBase):
    id: int
    is_active: bool
    is_verified: bool
    is_admin: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        orm_mode = True

class UserInDB(User):
    hashed_password: str

# User Settings Schemas
class UserSettingsBase(BaseModel):
    chart_theme: Optional[str] = "light"
    chart_type: Optional[str] = "candlestick"
    show_grid: Optional[bool] = True
    show_volume: Optional[bool] = False
    email_notifications: Optional[bool] = True
    trade_alerts: Optional[bool] = True
    report_frequency: Optional[str] = "weekly"

class UserSettingsCreate(UserSettingsBase):
    user_id: int

class UserSettingsUpdate(UserSettingsBase):
    pass

class UserSettings(UserSettingsBase):
    id: int
    user_id: int
    
    class Config:
        orm_mode = True

# Trade Schemas
class TradeBase(BaseModel):
    ticket: int
    symbol: str
    type: str  # BUY/SELL
    volume: float
    entry_price: float
    exit_price: float
    profit: float
    commission: Optional[float] = 0.0
    swap: Optional[float] = 0.0
    time: datetime
    time_close: Optional[datetime] = None
    sl: Optional[float] = None
    tp: Optional[float] = None

class TradeCreate(TradeBase):
    pips: Optional[float] = 0.0
    win: Optional[bool] = False
    win_rate: Optional[float] = 0.0
    notes: Optional[str] = None
    screenshot: Optional[str] = None
    tags: Optional[str] = None

class TradeUpdate(BaseModel):
    notes: Optional[str] = None
    tags: Optional[str] = None
    screenshot: Optional[str] = None

class Trade(TradeCreate):
    id: int
    user_id: int
    
    class Config:
        orm_mode = True

# Trade Statistics Schemas
class TradeStats(BaseModel):
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    total_profit: float = 0.0
    avg_profit: float = 0.0
    max_profit: float = 0.0
    max_loss: float = 0.0
    profit_factor: float = 0.0

class SymbolStats(BaseModel):
    symbol: str
    total_trades: int
    win_rate: float
    win_count: int  

    total_profit: float
    avg_profit: float

class HourlyStats(BaseModel):
    hour: int
    total_trades: int
    win_rate: float
    total_profit: float

# Token Schemas
class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class TokenData(BaseModel):
    email: Optional[str] = None

# Email Verification
class VerificationRequest(BaseModel):
    email: EmailStr

# Password Reset
class PasswordResetRequest(BaseModel):
    email: EmailStr

class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str

# Login
class LoginRequest(BaseModel):
    email: EmailStr
    password: str

# ========== NEW AI FEATURES SCHEMAS ==========

class BadgeType(str, Enum):
    BEST_TRADER = "best_trader"
    CONSISTENCY = "consistency"
    RISK_MANAGER = "risk_manager"
    HIGH_PROFIT = "high_profit"
    DISCIPLINED = "disciplined"
    COMEBACK_KING = "comeback_king"

class BadgeBase(BaseModel):
    badge_type: BadgeType
    description: Optional[str] = None

class BadgeCreate(BadgeBase):
    user_id: int

class Badge(BadgeBase):
    id: int
    user_id: int
    awarded_date: datetime
    
    class Config:
        orm_mode = True

class WeeklyReportBase(BaseModel):
    week_start: datetime
    week_end: datetime
    summary: Optional[str] = None
    performance_score: Optional[float] = None
    win_rate: Optional[float] = None
    total_trades: Optional[int] = None
    total_profit: Optional[float] = None
    avg_rrr: Optional[float] = None
    best_trade: Optional[Dict[str, Any]] = None
    worst_trade: Optional[Dict[str, Any]] = None
    recommendations: Optional[List[str]] = None
    patterns_identified: Optional[List[str]] = None
    sentiment_analysis: Optional[str] = None
    next_week_outlook: Optional[str] = None

class WeeklyReportCreate(WeeklyReportBase):
    user_id: int

class WeeklyReport(WeeklyReportBase):
    id: int
    user_id: int
    report_date: datetime
    
    class Config:
        orm_mode = True

class ChecklistItem(BaseModel):
    id: str
    text: str
    checked: bool = False
    required: bool = True

class TradeChecklistBase(BaseModel):
    name: str
    items: List[ChecklistItem]
    is_default: bool = False

class TradeChecklistCreate(TradeChecklistBase):
    user_id: int

class TradeChecklist(TradeChecklistBase):
    id: int
    user_id: int
    created_at: datetime
    
    class Config:
        orm_mode = True

class NewsAlertBase(BaseModel):
    symbol: Optional[str] = None
    title: str
    summary: Optional[str] = None
    impact: Optional[str] = None
    source: Optional[str] = None
    published_at: datetime

class NewsAlertCreate(NewsAlertBase):
    user_id: int

class NewsAlert(NewsAlertBase):
    id: int
    user_id: int
    created_at: datetime
    is_read: bool
    
    class Config:
        orm_mode = True

# Risk-Reward Analysis
class RiskRewardStats(BaseModel):
    avg_rrr: float = 0.0
    avg_winning_rrr: float = 0.0
    avg_losing_rrr: float = 0.0
    total_trades_analyzed: int = 0
    success_rate_by_range: Dict[str, Dict[str, Any]] = {}
    recommended_rrr: float = 1.5

# Trading Performance
class TradingPerformance(BaseModel):
    overall_performance: float = 0.0
    risk_management_score: float = 0.0
    consistency_score: float = 0.0
    profitability_score: float = 0.0
    discipline_score: float = 0.0