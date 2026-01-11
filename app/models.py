from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Text, ForeignKey, JSON, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from .database import Base

class BadgeType(str, enum.Enum):
    BEST_TRADER = "best_trader"
    CONSISTENCY = "consistency"
    RISK_MANAGER = "risk_manager"
    HIGH_PROFIT = "high_profit"
    DISCIPLINED = "disciplined"
    COMEBACK_KING = "comeback_king"

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String)
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # MT5 credentials (encrypted in production)
    mt5_server = Column(String)
    mt5_login = Column(Integer)
    mt5_password = Column(String)
    
    # User preferences
    theme = Column(String, default="light")  # light/dark
    timezone = Column(String, default="UTC")
    
    # Relationships
    trades = relationship("Trade", back_populates="user")
    user_settings = relationship("UserSettings", back_populates="user", uselist=False)
    badges = relationship("UserBadge", back_populates="user")
    weekly_reports = relationship("WeeklyReport", back_populates="user", order_by="desc(WeeklyReport.report_date)")
    trade_checklists = relationship("TradeChecklist", back_populates="user")
    news_alerts = relationship("NewsAlert", back_populates="user")

class UserSettings(Base):
    __tablename__ = "user_settings"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True)
    
    # Chart settings
    chart_theme = Column(String, default="light")  # light/dark
    chart_type = Column(String, default="candlestick")  # candlestick/line/bar
    show_grid = Column(Boolean, default=True)
    show_volume = Column(Boolean, default=False)
    
    # Notification settings
    email_notifications = Column(Boolean, default=True)
    trade_alerts = Column(Boolean, default=True)
    report_frequency = Column(String, default="weekly")  # daily/weekly/monthly
    
    # Risk management settings
    max_daily_loss = Column(Float, default=0.05)  # 5% max daily loss
    max_trade_risk = Column(Float, default=0.02)  # 2% max risk per trade
    min_rrr = Column(Float, default=1.5)  # Minimum risk-reward ratio
    
    user = relationship("User", back_populates="user_settings")

class Trade(Base):
    __tablename__ = "trades"
    
    id = Column(Integer, primary_key=True, index=True)
    ticket = Column(Integer, unique=True, index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"))
    
    # Trade details
    symbol = Column(String, index=True)
    type = Column(String)  # BUY/SELL
    volume = Column(Float)
    entry_price = Column(Float)
    exit_price = Column(Float)
    profit = Column(Float)
    commission = Column(Float)
    swap = Column(Float)
    time = Column(DateTime, index=True)
    time_close = Column(DateTime)
    
    # Risk management
    sl = Column(Float)  # Stop loss
    tp = Column(Float)  # Take profit
    
    # Calculated fields
    pips = Column(Float)
    win = Column(Boolean)
    win_rate = Column(Float)
    
    # User added fields
    notes = Column(Text)
    screenshot = Column(String)  # Path to screenshot
    tags = Column(String)  # Comma separated tags
    
    user = relationship("User", back_populates="trades")

class VerificationToken(Base):
    __tablename__ = "verification_tokens"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, index=True)
    token = Column(String, unique=True, index=True)
    expires_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)

class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, index=True)
    token = Column(String, unique=True, index=True)
    expires_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    used = Column(Boolean, default=False)

class UserBadge(Base):
    __tablename__ = "user_badges"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    badge_type = Column(Enum(BadgeType), nullable=False)
    awarded_date = Column(DateTime, default=datetime.utcnow)
    description = Column(String(500))
    
    user = relationship("User", back_populates="badges")

class WeeklyReport(Base):
    __tablename__ = "weekly_reports"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    week_start = Column(DateTime, nullable=False)
    week_end = Column(DateTime, nullable=False)
    report_date = Column(DateTime, default=datetime.utcnow)
    
    # AI-generated insights
    summary = Column(Text)
    performance_score = Column(Float)
    win_rate = Column(Float)
    total_trades = Column(Integer)
    total_profit = Column(Float)
    avg_rrr = Column(Float)  # Average Risk-Reward Ratio
    best_trade = Column(JSON)  # Store best trade details as JSON
    worst_trade = Column(JSON)  # Store worst trade details as JSON
    
    # AI recommendations
    recommendations = Column(JSON)
    patterns_identified = Column(JSON)
    sentiment_analysis = Column(Text)
    next_week_outlook = Column(Text)
    
    user = relationship("User", back_populates="weekly_reports")

class TradeChecklist(Base):
    __tablename__ = "trade_checklists"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    name = Column(String(200), nullable=False)
    items = Column(JSON)  # List of checklist items
    is_default = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", back_populates="trade_checklists")

class NewsAlert(Base):
    __tablename__ = "news_alerts"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    symbol = Column(String(50))
    title = Column(String(500), nullable=False)
    summary = Column(Text)
    impact = Column(String(50))  # high, medium, low
    source = Column(String(200))
    published_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_read = Column(Boolean, default=False)
    
    user = relationship("User", back_populates="news_alerts")