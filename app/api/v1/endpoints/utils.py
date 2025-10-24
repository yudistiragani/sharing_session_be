import os
from datetime import datetime, timezone
from typing import Optional, Callable
from fastapi import Depends, HTTPException, UploadFile
from fastapi.security import OAuth2PasswordBearer
from app.core.security import decode_token
from app.db.mongodb_config import get_db
from app.core.config import settings
from bson import ObjectId

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login")

async def get_current_user(token: str = Depends(oauth2_scheme), db=Depends(get_db)):
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    jti = payload.get("jti")
    sub = payload.get("sub")
    if not sub:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    # cek blacklist (logout)
    revoked = await db.revoked_tokens.find_one({"jti": jti})
    if revoked:
        raise HTTPException(status_code=401, detail="Token has been revoked")

    # load user (include role)
    try:
        user = await db.users.find_one({"_id": ObjectId(sub)}, {"hashed_password": 0})
    except Exception:
        user = None
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user

def require_roles(*roles: str) -> Callable:
    async def _checker(current_user=Depends(get_current_user)):
        if current_user.get("role") not in roles:
            raise HTTPException(status_code=403, detail="Insufficient role")
        return current_user
    return _checker

require_admin = require_roles("admin")

async def save_upload_file(file: UploadFile, base_dir: str, sub_dir: str, prefix: str = "") -> str:
    os.makedirs(os.path.join(base_dir, sub_dir), exist_ok=True)
    ext = os.path.splitext(file.filename or "")[1].lower() or ".bin"
    filename = f"{prefix}{int(datetime.now(timezone.utc).timestamp()*1000)}{ext}"
    rel_path = os.path.join(sub_dir, filename).replace("\\", "/")
    abs_path = os.path.join(base_dir, rel_path)

    content = await file.read()
    with open(abs_path, "wb") as f:
        f.write(content)
    return f"/uploads/{rel_path}"
