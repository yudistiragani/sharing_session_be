import time
import uuid
import jwt
from passlib.hash import pbkdf2_sha256
from typing import Optional
from app.core.config import settings

def hash_password(plain_password: str) -> str:
    # PBKDF2-SHA256 aman & simpel, tidak ada limit 72 bytes
    return pbkdf2_sha256.hash(plain_password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pbkdf2_sha256.verify(plain_password, hashed_password)

def create_access_token(subject: str, expires_minutes: int = settings.ACCESS_TOKEN_EXPIRE_MINUTES) -> dict:
    now = int(time.time())
    exp = now + expires_minutes * 60
    jti = str(uuid.uuid4())
    payload = {"sub": subject, "iat": now, "exp": exp, "jti": jti}
    token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return {"access_token": token, "token_type": "bearer", "exp": exp, "jti": jti}

def decode_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except jwt.PyJWTError:
        return None
