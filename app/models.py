# app/models.py
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean
from sqlalchemy.sql import func
from .database import Base

class Trade(Base):
    __tablename__ = "trades"
    
    id = Column(Integer, primary_key=True, index=True)
    ticket = Column(Integer, unique=True, index=True)
    position_id = Column(Integer)
    time = Column(DateTime)
    type = Column(String)  # 'BUY' or 'SELL'
    symbol = Column(String)
    volume = Column(Float)
    price = Column(Float)
    sl = Column(Float, nullable=True)
    tp = Column(Float, nullable=True)
    time_close = Column(DateTime, nullable=True)
    price_close = Column(Float, nullable=True)
    commission = Column(Float, default=0)
    swap = Column(Float, default=0)
    profit = Column(Float)
    comment = Column(String, nullable=True)
    
    duration_minutes = Column(Integer, nullable=True)
    pips = Column(Float, nullable=True)
    win = Column(Boolean, nullable=True)
    
    synced_at = Column(DateTime, default=func.now())

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    is_active = Column(Boolean, default=True)