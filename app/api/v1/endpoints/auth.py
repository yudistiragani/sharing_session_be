from fastapi import APIRouter, Depends, HTTPException, status, Body
from fastapi.security import OAuth2PasswordRequestForm
from datetime import datetime, timezone
from bson import ObjectId
from app.core.security import create_access_token, verify_password, hash_password, decode_token
from app.db.mongodb_config import get_db

router = APIRouter(tags=["Auth"])


@router.post("/register")
async def register_user(
    email: str = Body(..., embed=True),
    password: str = Body(..., embed=True),
    full_name: str | None = Body(None, embed=True),
    phone_number: str | None = Body(None, embed=True),
    db=Depends(get_db),
):
    existing = await db.users.find_one({"email": email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    has_admin = await db.users.find_one({"role": "admin"}) is not None
    role = "user" if has_admin else "admin"

    now = datetime.now(timezone.utc)
    doc = {
        "email": email,
        "full_name": full_name,
        "phone_number": phone_number,
        "profile_image": None,
        "role": role,
        "status": "active",
        "hashed_password": hash_password(password),
        "created_at": now,
        "updated_at": now,
    }
    res = await db.users.insert_one(doc)
    user = await db.users.find_one({"_id": res.inserted_id}, {"hashed_password": 0})
    user["_id"] = str(user["_id"])
    return {"message": "Registered", "user": user}


@router.post("/login")
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db=Depends(get_db)
):
    user = await db.users.find_one({"email": form_data.username})
    if not user or not verify_password(form_data.password, user["hashed_password"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")

    token_data = create_access_token(str(user["_id"]))
    # kirim juga role agar client-side bisa menyesuaikan UI
    token_data["role"] = user.get("role", "user")
    return token_data

@router.post("/logout")
async def logout(token: str = Body(..., embed=True), db=Depends(get_db)):
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    jti = payload.get("jti")
    exp = payload.get("exp")
    if not jti or not exp:
        raise HTTPException(status_code=400, detail="Bad token payload")

    from datetime import datetime, timezone
    expires_at = datetime.fromtimestamp(exp, tz=timezone.utc)
    await db.revoked_tokens.update_one(
        {"jti": jti},
        {"$set": {"jti": jti, "expiresAt": expires_at}},
        upsert=True
    )
    return {"message": "Logged out"}
