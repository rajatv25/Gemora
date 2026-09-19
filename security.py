import os

from passlib.context import CryptContext
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import func, select 
from sqlalchemy.orm import session
from model import User
from database import get_db
from datetime import datetime, timedelta, timezone
from jose import jwt,JWTError
from password_policy import validate_password_length

secret_key = os.getenv("SECRET_KEY", "dev-only-change-me")
ALGORITHM="HS256"
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

oauth2_scehme=OAuth2PasswordBearer(tokenUrl="/login")

def hash_password(plain_password):
    validate_password_length(plain_password)
    return pwd_context.hash(plain_password[:72])

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password[:72], hashed_password)

def create_acces_token(data: dict):
    # Logic to create access token
    to_encode = data.copy()

    # Add expiration time to the token
    # For example, you can use datetime and timedelta to set an expiration time
    expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})

    # Encode the token
    encoded_jwt = jwt.encode(to_encode, secret_key, algorithm=ALGORITHM)
    return encoded_jwt

def get_current_user(token:str= Depends(oauth2_scehme),db:session=Depends(get_db)):

    try:
        payload = jwt.decode(
            token,
            secret_key,
            algorithms=[ALGORITHM]
        )

        email = (payload.get("sub") or "").strip().lower()

        if not email:
            raise HTTPException(
                status_code=401,
                detail='invalid token'
            )

        #user finding from db
        user = db.execute(select(User).where(func.lower(User.email) == email)).scalar_one_or_none()

        if not user:
            raise HTTPException(
                status_code=401,
                detail='invalid token'
            )
        return user

    except JWTError:
        raise HTTPException(
            status_code=401,
            detail='invalid token or expired token'

        )