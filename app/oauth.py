# app/oauth.py
import secrets
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import httpx
from jose import JWTError, jwt
from urllib.parse import urlencode

from .config import settings

class GoogleOAuth:
    """Google OAuth 2.0 client"""
    
    def __init__(self):
        self.config = settings.google_oauth_config
    
    def get_authorization_url(self, state: Optional[str] = None) -> str:
        """Generate Google OAuth authorization URL"""
        if not state:
            state = secrets.token_urlsafe(32)
        
        params = {
            "client_id": self.config["client_id"],
            "redirect_uri": self.config["redirect_uri"],
            "response_type": "code",
            "scope": " ".join(self.config["scopes"]),
            "state": state,
            "access_type": "offline",  # To get refresh token
            "prompt": "consent select_account"  # Force consent screen
        }
        
        return f"{self.config['authorize_url']}?{urlencode(params)}"
    
    async def get_tokens(self, code: str) -> Dict[str, Any]:
        """Exchange authorization code for tokens"""
        if not settings.is_google_oauth_configured:
            raise ValueError("Google OAuth is not configured")
        
        token_data = {
            "code": code,
            "client_id": self.config["client_id"],
            "client_secret": self.config["client_secret"],
            "redirect_uri": self.config["redirect_uri"],
            "grant_type": "authorization_code"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.config["token_url"],
                data=token_data,
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            
            if response.status_code != 200:
                error_detail = response.json().get("error_description", "Unknown error")
                raise ValueError(f"Failed to get tokens: {error_detail}")
            
            return response.json()
    
    async def get_user_info(self, access_token: str) -> Dict[str, Any]:
        """Get user info from Google API"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                self.config["userinfo_url"],
                headers={"Authorization": f"Bearer {access_token}"}
            )
            
            if response.status_code != 200:
                raise ValueError("Failed to get user info")
            
            return response.json()
    
    def create_state_token(self, data: Dict[str, Any]) -> str:
        """Create a state token for OAuth flow"""
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(minutes=10)
        to_encode.update({"exp": expire})
        return jwt.encode(to_encode, settings.OAUTH_STATE_SECRET, algorithm="HS256")
    
    def verify_state_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Verify and decode state token"""
        try:
            payload = jwt.decode(token, settings.OAUTH_STATE_SECRET, algorithms=["HS256"])
            return payload
        except JWTError:
            return None
    
    async def validate_oauth_flow(self, code: str) -> Dict[str, Any]:
        """Complete OAuth flow: get tokens and user info"""
        # Get tokens
        tokens = await self.get_tokens(code)
        access_token = tokens.get("access_token")
        
        if not access_token:
            raise ValueError("No access token received")
        
        # Get user info
        user_info = await self.get_user_info(access_token)
        
        return {
            "user_info": user_info,
            "tokens": tokens,
            "email": user_info.get("email"),
            "name": user_info.get("name"),
            "picture": user_info.get("picture"),
            "google_id": user_info.get("sub")
        }

# Create global instance
google_oauth = GoogleOAuth()