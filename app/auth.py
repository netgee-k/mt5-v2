# app/auth.py - NO PASSLIB VERSION
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
import hashlib
import os
from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-this-in-production")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 30))

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Simple password verification without passlib"""
    try:
        # Check if hash is in our simple format
        if not hashed_password or ':' not in hashed_password:
            return False
        
        algo, stored_hash = hashed_password.split(':', 1)
        
        if algo == 'sha256':
            # Compute SHA256 hash of the password
            computed_hash = hashlib.sha256(plain_password.encode()).hexdigest()
            return stored_hash == computed_hash
        
        return False
    except Exception:
        return False

def get_password_hash(password: str) -> str:
    """Simple password hashing without passlib"""
    hash_obj = hashlib.sha256(password.encode())
    hex_hash = hash_obj.hexdigest()
    return f"sha256:{hex_hash}"

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt