from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from .database import Base

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
    
    trades = relationship("Trade", back_populates="user")
    user_settings = relationship("UserSettings", back_populates="user", uselist=False)

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