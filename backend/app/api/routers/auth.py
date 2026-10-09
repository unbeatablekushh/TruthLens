from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from datetime import datetime
from uuid import UUID
from app.core.database import get_db
from app.core.security import (
    get_password_hash,
    verify_password,
    create_access_token,
    create_refresh_token,
    verify_refresh_token,
    pwd_context
)
from app.core.rate_limit import login_rate_limiter, register_rate_limiter
from app.models.auth import User, RefreshToken, Role
from app.schemas.auth import UserCreate, UserLogin, UserResponse, Token, RefreshTokenRequest
from app.api.deps import get_current_active_user, get_current_user
from app.services.audit import log_audit_event
import uuid

router = APIRouter(prefix="/api/auth", tags=["auth"])

@router.post("/register", response_model=UserResponse, dependencies=[Depends(register_rate_limiter)])
def register_user(user_in: UserCreate, request: Request, db: Session = Depends(get_db)):
    if user_in.password != user_in.confirm_password:
        raise HTTPException(status_code=400, detail="Passwords do not match")
        
    # Check duplicate
    existing_user = db.query(User).filter(User.email == user_in.email.lower()).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
        
    hashed_password = get_password_hash(user_in.password)
    
    new_user = User(
        name=user_in.name,
        email=user_in.email.lower(),
        password_hash=hashed_password,
        role=Role.USER,
        is_active=True
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    log_audit_event(
        db=db,
        event_type="USER_REGISTERED",
        user_id=new_user.id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent")
    )
    
    return new_user

@router.post("/login", response_model=Token, dependencies=[Depends(login_rate_limiter)])
def login_user(user_credentials: UserLogin, request: Request, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == user_credentials.email.lower()).first()
    
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    
    if not user or not verify_password(user_credentials.password, user.password_hash):
        if user:
            log_audit_event(db, "USER_LOGIN_FAILED", user.id, ip_address, user_agent)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")

    # Update last login
    user.last_login_at = datetime.utcnow()
    
    # Create tokens
    access_token = create_access_token(subject=str(user.id), role=user.role.value)
    refresh_token = create_refresh_token(subject=str(user.id))
    
    # Store refresh token hash securely
    token_hash = get_password_hash(refresh_token)
    payload = verify_refresh_token(refresh_token)
    
    new_rt = RefreshToken(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=datetime.fromtimestamp(payload["exp"])
    )
    db.add(new_rt)
    db.commit()
    
    log_audit_event(db, "USER_LOGIN", user.id, ip_address, user_agent)
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": user
    }

@router.post("/refresh", response_model=Token, dependencies=[Depends(login_rate_limiter)])
def refresh_access_token(token_request: RefreshTokenRequest, request: Request, db: Session = Depends(get_db)):
    payload = verify_refresh_token(token_request.refresh_token)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
        
    user_id_str = payload.get("sub")
    
    # Convert string UUID to UUID object
    try:
        user_id = UUID(user_id_str)
    except (ValueError, TypeError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token format")
    
    # Find matching active refresh token by hashing and checking against DB
    user_tokens = db.query(RefreshToken).filter(
        RefreshToken.user_id == user_id,
        RefreshToken.revoked == False,
        RefreshToken.expires_at > datetime.utcnow()
    ).all()
    
    matching_db_token = None
    for rt in user_tokens:
        if pwd_context.verify(token_request.refresh_token, rt.token_hash):
            matching_db_token = rt
            break
            
    if not matching_db_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or revoked refresh token")
        
    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User inactive or deleted")

    # Rotate refresh token
    matching_db_token.revoked = True
    
    new_access_token = create_access_token(subject=str(user.id), role=user.role.value)
    new_refresh_token = create_refresh_token(subject=str(user.id))
    
    new_token_hash = get_password_hash(new_refresh_token)
    new_payload = verify_refresh_token(new_refresh_token)
    
    new_rt = RefreshToken(
        user_id=user.id,
        token_hash=new_token_hash,
        expires_at=datetime.fromtimestamp(new_payload["exp"])
    )
    db.add(new_rt)
    db.commit()
    
    log_audit_event(
        db, "TOKEN_REFRESHED", user.id, 
        request.client.host if request.client else None, 
        request.headers.get("user-agent")
    )
    
    return {
        "access_token": new_access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer",
        "user": user
    }

@router.post("/logout")
def logout(token_request: RefreshTokenRequest, request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Find and revoke the specific refresh token
    user_tokens = db.query(RefreshToken).filter(
        RefreshToken.user_id == current_user.id,
        RefreshToken.revoked == False
    ).all()
    
    for rt in user_tokens:
        if pwd_context.verify(token_request.refresh_token, rt.token_hash):
            rt.revoked = True
            break
            
    db.commit()
    
    log_audit_event(
        db, "USER_LOGOUT", current_user.id, 
        request.client.host if request.client else None, 
        request.headers.get("user-agent")
    )
    return {"message": "Successfully logged out"}

@router.get("/me", response_model=UserResponse)
def read_users_me(current_user: User = Depends(get_current_active_user)):
    return current_user
