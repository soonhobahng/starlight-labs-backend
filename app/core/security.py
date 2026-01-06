from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.database import get_db
from app.models.models import User
import logging

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()

# Logger 설정
logger = logging.getLogger(__name__)


def get_password_hash(password: str) -> str:
    logger.debug(f"Password length: {len(password)}")
    logger.debug(f"Password bytes length: {len(password.encode('utf-8'))}")
    logger.debug(f"Password repr: {repr(password)}")
    
    # Truncate password to 72 bytes for bcrypt compatibility
    password_bytes = password.encode('utf-8')
    if len(password_bytes) > 72:
        logger.debug(f"Truncating password from {len(password_bytes)} bytes to 72 bytes")
        password_bytes = password_bytes[:72]
        password = password_bytes.decode('utf-8', errors='ignore')
    
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
    return encoded_jwt


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    logger.debug(f"Received credentials: {credentials}")
    logger.debug(f"Token: {credentials.credentials if credentials else 'None'}")
    
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        logger.debug(f"Using secret_key: {settings.secret_key[:10]}...")
        logger.debug(f"Using algorithm: {settings.algorithm}")
        
        payload = jwt.decode(credentials.credentials, settings.secret_key, algorithms=[settings.algorithm])
        logger.debug(f"Decoded payload: {payload}")
        
        user_id: str = payload.get("sub")
        logger.debug(f"Extracted user_id: {user_id}")
        
        if user_id is None:
            logger.debug("user_id is None")
            raise credentials_exception
    except JWTError as e:
        logger.debug(f"JWT Error: {e}")
        raise credentials_exception
    
    user = db.query(User).filter(User.id == user_id).first()
    logger.debug(f"Found user: {user.email if user else 'None'}")
    
    if user is None:
        logger.debug("User not found in database")
        raise credentials_exception
    return user