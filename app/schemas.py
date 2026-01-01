from pydantic import BaseModel, ConfigDict, EmailStr
from typing import Optional, List
from datetime import datetime

# User schemas
class UserBase(BaseModel):
    email: EmailStr
    username: Optional[str] = None
    full_name: Optional[str] = None

class UserCreate(UserBase):
    password: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserUpdate(BaseModel):
    username: Optional[str] = None
    full_name: Optional[str] = None
    current_password: Optional[str] = None
    new_password: Optional[str] = None

class UserMT5Credentials(BaseModel):
    mt5_server: str
    mt5_login: int
    mt5_password: str

class UserSettingsUpdate(BaseModel):
    theme: Optional[str] = None
    timezone: Optional[str] = None
    chart_theme: Optional[str] = None
    chart_type: Optional[str] = None
    show_grid: Optional[bool] = None
    show_volume: Optional[bool] = None
    email_notifications: Optional[bool] = None
    trade_alerts: Optional[bool] = None

class UserInDB(UserBase):
    id: int
    is_active: bool
    is_verified: bool
    is_admin: bool
    created_at: datetime
    mt5_server: Optional[str] = None
    mt5_login: Optional[int] = None
    
    # FIX: Use model_config instead of inner Config class
    model_config = ConfigDict(from_attributes=True)

class UserResponse(UserInDB):
    pass

# Token schemas
class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class TokenData(BaseModel):
    email: Optional[str] = None

# Email schemas
class EmailSchema(BaseModel):
    email: List[EmailStr]

# Trade schemas (updated)
class TradeBase(BaseModel):
    ticket: int
    symbol: str
    type: str
    volume: float
    entry_price: float
    exit_price: float
    profit: float
    commission: float
    swap: float
    time: datetime
    time_close: Optional[datetime] = None

class TradeCreate(TradeBase):
    notes: Optional[str] = None
    tags: Optional[str] = None

class TradeUpdate(BaseModel):
    notes: Optional[str] = None
    tags: Optional[str] = None
    screenshot: Optional[str] = None

class TradeInDB(TradeBase):
    id: int
    user_id: int
    pips: float = 0.0  # FIX: Added default value
    win: bool = False   # FIX: Added default value
    win_rate: float = 0.0  # FIX: Added default value
    notes: Optional[str] = None
    tags: Optional[str] = None
    screenshot: Optional[str] = None
    sl: Optional[float] = None  # Added missing field
    tp: Optional[float] = None  # Added missing field
    
    # FIX: Use model_config instead of orm_mode
    model_config = ConfigDict(from_attributes=True)

# Stats schemas
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
    win_count: int = 0  
    loss_count: int = 0
    win_rate: float
    total_profit: float
    avg_profit: float

class HourlyStats(BaseModel):
    hour: int
    total_trades: int
    win_rate: float
    total_profit: float