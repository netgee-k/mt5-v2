# app/routers/google_auth.py
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from fastapi.responses import RedirectResponse, HTMLResponse
from sqlalchemy.orm import Session
import secrets
import time

from app.database import get_db
from app import crud, schemas, auth
from app.oauth import google_oauth
from app.config import settings

router = APIRouter()

@router.get("/google/login")
async def login_with_google(request: Request):
    """Initiate Google OAuth login"""
    if not settings.is_google_oauth_configured:
        return HTMLResponse("""
            <html>
                <body style="font-family: Arial, sans-serif; padding: 40px; text-align: center;">
                    <h2>Google OAuth Not Configured</h2>
                    <p>Please configure Google OAuth in your .env file:</p>
                    <pre>GOOGLE_CLIENT_ID=your_client_id
GOOGLE_CLIENT_SECRET=your_client_secret</pre>
                    <a href="/login" style="color: blue;">← Back to Login</a>
                </body>
            </html>
        """)
    
    # Generate state for CSRF protection
    state = secrets.token_urlsafe(32)
    
    # Store state in cookie - SIMPLIFIED FOR LOCALHOST
    response = RedirectResponse(url=google_oauth.get_authorization_url(state))
    response.set_cookie(
        key="oauth_state",
        value=state,
        httponly=False,  # Changed to False for debugging
        max_age=600,
        secure=False,  # Must be False for localhost (http)
        samesite="lax",
        path="/"  # Explicitly set path
    )
    
    # DEBUG
    print(f"GOOGLE LOGIN: Setting cookie: oauth_state={state[:10]}...")
    
    return response

@router.get("/google/callback")
async def google_auth_callback(
    request: Request,
    code: str = Query(...),
    state: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Handle Google OAuth callback"""
    try:
        # DEBUG
        print(f"CALLBACK: Received state from Google: {state}")
        print(f"CALLBACK: All cookies: {dict(request.cookies)}")
        
        # Verify state to prevent CSRF
        stored_state = request.cookies.get("oauth_state")
        
        if not state:
            print("ERROR: No state parameter from Google")
            raise HTTPException(status_code=400, detail="No state parameter received")
        
        if not stored_state:
            print("ERROR: No oauth_state cookie found")
            # Try to get from session or alternative storage
            raise HTTPException(status_code=400, detail="Session expired or invalid")
        
        if state != stored_state:
            print(f"ERROR: State mismatch! Google: {state}, Cookie: {stored_state}")
            raise HTTPException(status_code=400, detail="Invalid state parameter")
        
        print(f"SUCCESS: State validated: {state[:10]}...")
        
        # Complete OAuth flow
        oauth_data = await google_oauth.validate_oauth_flow(code)
        
        google_email = oauth_data["email"]
        google_name = oauth_data["name"]
        google_id = oauth_data["google_id"]
        
        if not google_email:
            raise HTTPException(status_code=400, detail="No email received from Google")
        
        # Check if user exists
        user = crud.get_user_by_email(db, google_email)
        
        if not user:
            # Create new user
            username_base = google_email.split('@')[0]
            username = f"{username_base}_{int(time.time())}"
            
            # Create user with OAuth flag
            user_create = schemas.UserCreate(
                email=google_email,
                username=username,
                full_name=google_name or username,
                password="oauth_user_password_not_required",
                is_oauth_user=True
            )
            
            user = crud.create_user(db, user_create)
            
        # Store OAuth info
        if not user.oauth_id or user.oauth_provider != "google":
            user.oauth_provider = "google"
            user.oauth_id = google_id
            db.add(user)
            db.commit()
            db.refresh(user)
        
        # Create JWT token
        access_token = auth.create_access_token(data={"sub": user.email})
        
        # Get FRONTEND_URL
        frontend_url = settings.FRONTEND_URL.rstrip('/')
        
        # Redirect to dashboard
        redirect_url = f"{frontend_url}/dashboard"
        
        response = RedirectResponse(url=redirect_url)
        response.delete_cookie("oauth_state", path="/")
        
        # Set access token cookie
        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,
            max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            secure=False,
            samesite="lax",
            path="/"
        )
        
        print(f"SUCCESS: User {google_email} logged in via Google")
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print(f"OAuth error: {e}")
        print(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=400, detail="Authentication failed")