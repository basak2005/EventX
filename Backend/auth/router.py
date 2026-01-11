from fastapi import APIRouter, HTTPException, Response, Cookie, Header
from fastapi.responses import RedirectResponse
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import os
import secrets
from typing import Optional
from config import (
    GOOGLE_CLIENT_ID,
    GOOGLE_CLIENT_SECRET,
    GOOGLE_REDIRECT_URI,
    SCOPES,
    FRONTEND_URL,
)
from database import save_credentials, load_credentials, delete_credentials, get_all_users

# Allow scope changes (Google adds 'openid' automatically)
os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"

# Session cookie name
SESSION_COOKIE_NAME = "session_id"

# Check if we're in production (HTTPS)
IS_PRODUCTION = os.getenv("VERCEL_ENV") is not None or FRONTEND_URL.startswith("https://")

def get_cookie_settings():
    """Get cookie settings based on environment for cross-site cookies"""
    return {
        "httponly": True,
        "secure": IS_PRODUCTION,  # True for HTTPS
        "samesite": "none" if IS_PRODUCTION else "lax",  # 'none' for cross-site
        "path": "/",
        "max_age": 60 * 60 * 24 * 7,  # 7 days
    }

# In-memory cache per session (for serverless, this resets, so we rely on MongoDB)
credentials_cache = {}


def extract_session_id(
    session_cookie: Optional[str] = None,
    authorization: Optional[str] = None
) -> Optional[str]:
    """Extract session ID from cookie or Authorization header"""
    # Check Authorization header first (for cross-origin requests)
    if authorization:
        if authorization.startswith("Bearer "):
            return authorization[7:]
        return authorization
    # Fall back to cookie
    return session_cookie


def get_user_email_from_credentials(credentials):
    """Get the user's email from Google using credentials"""
    try:
        service = build('oauth2', 'v2', credentials=credentials)
        user_info = service.userinfo().get().execute()
        return user_info.get('email')
    except Exception as e:
        print(f"Error getting user email: {e}")
        return None


def get_credentials(session_id: Optional[str] = None):
    """Get credentials for a specific session/user"""
    if not session_id:
        return None
    
    # Check memory cache first
    if session_id in credentials_cache:
        creds = credentials_cache[session_id]
        # Refresh if expired
        if creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                save_credentials(creds, session_id)
                credentials_cache[session_id] = creds
            except Exception as e:
                print(f"Error refreshing token: {e}")
                # Token refresh failed, remove from cache
                del credentials_cache[session_id]
                return None
        return creds
    
    # Try loading from database using session_id as user identifier
    creds = load_credentials(session_id)
    if creds:
        # Refresh if expired
        if creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                save_credentials(creds, session_id)
            except Exception as e:
                print(f"Error refreshing token: {e}")
                return None
        credentials_cache[session_id] = creds
        return creds
    
    return None


router = APIRouter()


@router.get("/login")
def login(
    redirect: bool = True, 
    force: bool = False,
    response: Response = None,
    session_id: Optional[str] = Cookie(None, alias=SESSION_COOKIE_NAME)
):
    """
    Start Google OAuth login.
    - Each user gets their own session
    - If redirect=True (default): Automatically redirects to Google login
    - If redirect=False: Returns the auth URL as JSON
    - If force=True: Forces re-authentication even if already logged in
    """
    # Check if already authenticated for this session
    if not force and session_id:
        creds = get_credentials(session_id)
        if creds and not creds.expired:
            if redirect:
                redirect_response = RedirectResponse(url=f"{FRONTEND_URL}?authenticated=true")
                # Refresh the cookie with proper settings
                cookie_settings = get_cookie_settings()
                redirect_response.set_cookie(
                    key=SESSION_COOKIE_NAME,
                    value=session_id,
                    **cookie_settings
                )
                return redirect_response
            return {
                "message": "Already authenticated!",
                "authenticated": True,
                "session_id": session_id,
                "hint": "Use /auth/login?force=true to re-authenticate"
            }
    
    # Generate a new state parameter that includes a new session ID
    new_session_id = secrets.token_urlsafe(32)
    
    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        },
        scopes=SCOPES,
    )

    flow.redirect_uri = GOOGLE_REDIRECT_URI

    # Use state parameter to pass session ID through OAuth flow
    auth_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
        state=new_session_id,  # Pass session ID in state
    )

    if redirect:
        return RedirectResponse(url=auth_url)
    
    return {"auth_url": auth_url, "session_id": new_session_id}


@router.get("/callback")
def callback(code: str, state: str, response: Response):
    """
    OAuth callback - Google redirects here with authorization code
    State parameter contains the session ID
    """
    try:
        session_id = state  # Session ID passed through OAuth state
        
        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": GOOGLE_CLIENT_ID,
                    "client_secret": GOOGLE_CLIENT_SECRET,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                }
            },
            scopes=SCOPES,
        )

        flow.redirect_uri = GOOGLE_REDIRECT_URI
        flow.fetch_token(code=code)

        credentials = flow.credentials
        
        # Store in memory cache with session ID
        credentials_cache[session_id] = credentials
        
        # Persist to MongoDB database with session ID as key
        save_credentials(credentials, session_id)
        
        # Create redirect response to frontend
        redirect_url = f"{FRONTEND_URL}?session_id={session_id}&authenticated=true"
        redirect_response = RedirectResponse(url=redirect_url, status_code=302)
        
        # Set the session cookie with proper cross-site settings BEFORE redirect
        cookie_settings = get_cookie_settings()
        redirect_response.set_cookie(
            key=SESSION_COOKIE_NAME,
            value=session_id,
            **cookie_settings
        )
        
        return redirect_response
        
    except Exception as e:
        print(f"❌ OAuth callback error: {e}")
        raise HTTPException(status_code=500, detail=f"OAuth callback failed: {str(e)}")
        
    except Exception as e:
        print(f"❌ OAuth callback error: {e}")
        raise HTTPException(status_code=500, detail=f"OAuth callback failed: {str(e)}")


@router.get("/success")
def auth_success(
    session_cookie: Optional[str] = Cookie(None, alias=SESSION_COOKIE_NAME),
    authorization: Optional[str] = Header(None)
):
    """Success page after authentication"""
    session_id = extract_session_id(session_cookie, authorization)
    creds = get_credentials(session_id)
    if creds:
        user_email = get_user_email_from_credentials(creds)
        return {
            "message": "✅ Authentication successful!",
            "status": "logged_in",
            "user_email": user_email,
            "session_persisted": True,
            "token_expiry": str(creds.expiry) if creds.expiry else None,
        }
    return {"message": "Not authenticated", "status": "logged_out"}


@router.get("/status")
def auth_status(
    session_cookie: Optional[str] = Cookie(None, alias=SESSION_COOKIE_NAME),
    authorization: Optional[str] = Header(None)
):
    """Check if user is authenticated"""
    session_id = extract_session_id(session_cookie, authorization)
    creds = get_credentials(session_id)
    if creds:
        user_email = get_user_email_from_credentials(creds)
        return {
            "authenticated": True,
            "expired": creds.expired,
            "expiry": str(creds.expiry) if creds.expiry else None,
            "user_email": user_email,
        }
    return {"authenticated": False}


@router.post("/logout")
def logout(
    response: Response,
    session_cookie: Optional[str] = Cookie(None, alias=SESSION_COOKIE_NAME),
    authorization: Optional[str] = Header(None)
):
    """Clear stored credentials for current user session"""
    session_id = extract_session_id(session_cookie, authorization)
    if session_id:
        # Remove from memory cache
        if session_id in credentials_cache:
            del credentials_cache[session_id]
        # Remove from database
        delete_credentials(session_id)
    
    # Clear the session cookie with proper cross-site settings
    cookie_settings = get_cookie_settings()
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        path=cookie_settings["path"],
        secure=cookie_settings["secure"],
        samesite=cookie_settings["samesite"],
    )
    
    return {"message": "Logged out successfully"}


@router.get("/users")
def list_users():
    """List all authenticated users (admin endpoint)"""
    return {"users": get_all_users()}


@router.post("/set-session")
def set_session(response: Response, session_id: str):
    """
    Set session cookie from session_id (for frontend to call after OAuth redirect).
    This is useful when the frontend receives the session_id in the URL and needs
    to set it as a proper cross-site cookie.
    """
    # Verify the session_id is valid
    creds = get_credentials(session_id)
    if not creds:
        raise HTTPException(status_code=401, detail="Invalid session_id")
    
    # Set the session cookie with proper cross-site settings
    cookie_settings = get_cookie_settings()
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_id,
        **cookie_settings
    )
    
    user_email = get_user_email_from_credentials(creds)
    return {
        "message": "Session cookie set successfully",
        "authenticated": True,
        "user_email": user_email,
    }


@router.get("/cookie-test")
def cookie_test(
    response: Response,
    session_cookie: Optional[str] = Cookie(None, alias=SESSION_COOKIE_NAME),
):
    """Debug endpoint to test cookie settings"""
    cookie_settings = get_cookie_settings()
    return {
        "received_session_cookie": session_cookie,
        "cookie_settings": cookie_settings,
        "is_production": IS_PRODUCTION,
        "frontend_url": FRONTEND_URL,
    }


