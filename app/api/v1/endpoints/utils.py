import os

from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Callable, Sequence, List
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


def _public_upload_to_abs(public_path: Optional[str]) -> Optional[Path]:
    """
    Konversi path public '/uploads/xxx' -> absolute path di filesystem.
    Return None jika formatnya tidak valid / di luar UPLOAD_DIR.
    """
    if not public_path or not public_path.startswith("/uploads/"):
        return None
    # buang prefix route '/uploads/' lalu gabungkan dengan folder fisik settings.UPLOAD_DIR
    rel = public_path[len("/uploads/"):]
    base = Path(settings.UPLOAD_DIR).resolve()
    cand = (base / rel).resolve()
    try:
        # Python 3.10+: pastikan masih di bawah base
        if not str(cand).startswith(str(base)):
            return None
    except Exception:
        return None
    return cand

def delete_public_upload_safe(public_path: Optional[str]) -> bool:
    """
    Hapus file upload berdasarkan path public ('/uploads/...').
    Mengembalikan True jika berhasil dihapus, False jika tidak ada / gagal (tanpa raise).
    """
    p = _public_upload_to_abs(public_path)
    if not p:
        return False
    try:
        if p.exists() and p.is_file():
            p.unlink()
            return True
    except Exception:
        pass
    return False


async def normalize_upload_list(files: Optional[Sequence[UploadFile | None]]) -> List[UploadFile]:
    """
    Buang item kosong/invalid dari array file (Swagger kadang kirim 'images=' jadi string kosong).
    Return hanya UploadFile valid dengan filename & isi > 0 byte.
    """
    out: List[UploadFile] = []
    if not files:
        return out
    for f in files:
        if not f or not getattr(f, "filename", ""):
            continue
        # Peek 1 byte untuk pastikan tidak kosong
        pos = await f.seek(0, 1)  # dapatkan posisi saat ini (untuk kompat)
        await f.seek(0)
        head = await f.read(1)
        await f.seek(0)
        if not head:
            continue
        out.append(f)
    return out


def encode_mongo(obj):
    """
    Recursively convert Mongo types so FastAPI can JSON-encode them.
    - ObjectId -> str
    - datetime -> isoformat
    - list/dict -> traverse
    """
    if isinstance(obj, ObjectId):
        return str(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, list):
        return [encode_mongo(x) for x in obj]
    if isinstance(obj, dict):
        return {k: encode_mongo(v) for k, v in obj.items()}
    return obj