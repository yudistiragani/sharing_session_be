import os

from typing import Optional, Any
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from bson import ObjectId
from datetime import datetime, timezone
from app.db.mongodb_config import get_db
from app.core.config import settings
from app.core.security import create_access_token, verify_password, hash_password, decode_token
from app.api.v1.endpoints.utils import get_current_user, save_upload_file, require_admin

router = APIRouter(tags=["Users"])


@router.post("")
async def create_user(
    email: str = Form(...),
    password: str = Form(...),
    full_name: str | None = Form(None),
    phone_number: str | None = Form(None),
    role: str = Form("user", pattern="^(admin|user)$"),
    status: str = Form("active", pattern="^(active|inactive)$"),
    profile_image: UploadFile = File(None),
    db=Depends(get_db),
):
    existing = await db.users.find_one({"email": email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already exists")

    # Simpan gambar jika ada
    image_path = None
    if profile_image is not None and profile_image.filename:
        image_path = await save_upload_file(
            profile_image,
            base_dir=settings.UPLOAD_DIR,
            sub_dir=settings.USER_UPLOAD_SUBDIR,
            prefix=f"user_{email.replace('@','_')}_"
        )

    now = datetime.now(timezone.utc)
    doc = {
        "email": email,
        "full_name": full_name,
        "phone_number": phone_number,
        "profile_image": image_path,
        "role": role,
        "status": status,
        "hashed_password": hash_password(password),
        "created_at": now,
        "updated_at": now,
    }
    res = await db.users.insert_one(doc)
    user = await db.users.find_one({"_id": res.inserted_id}, {"hashed_password": 0})
    user["_id"] = str(user["_id"])
    return {"message": "User created successfully", "user": user}


@router.get("", dependencies=[Depends(require_admin)])
async def list_users(
    db=Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    search: Optional[str] = Query(None, description="Cari by email/full_name"),
    role: Optional[str] = Query(None, pattern="^(admin|user)$"),
    status: Optional[str] = Query(None, pattern="^(active|inactive)$"),
    phone: Optional[str] = Query(None, description="Filter nomor HP; partial/contains, case-insensitive"),
):
    q = {}
    ands = []
    if search:
        ands.append({"$or": [
            {"email": {"$regex": search, "$options": "i"}},
            {"full_name": {"$regex": search, "$options": "i"}}
        ]})
    if role:
        ands.append({"role": role})
    if status:
        ands.append({"status": status})
    if phone:
        # contains (partial), case-insensitive
        ands.append({"phone_number": {"$regex": phone, "$options": "i"}})

    if ands:
        q = {"$and": ands}

    total = await db.users.count_documents(q)
    cursor = (
        db.users.find(q, {"hashed_password": 0})
        .skip((page - 1) * page_size)
        .limit(page_size)
        .sort("created_at", -1)
    )
    items = []
    async for doc in cursor:
        doc["_id"] = str(doc["_id"])
        items.append(doc)
    pages = (total + page_size - 1) // page_size
    return {"items": items, "meta": {"total": total, "page": page, "page_size": page_size, "pages": pages}}


@router.get("/{user_id}")
async def get_user(user_id: str, db=Depends(get_db), current_user=Depends(get_current_user)):
    if not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=400, detail="Invalid user id")
    # self or admin
    if str(current_user["_id"]) != user_id and current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Forbidden")
    doc = await db.users.find_one({"_id": ObjectId(user_id)}, {"hashed_password": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="User not found")
    doc["_id"] = str(doc["_id"])
    return doc


@router.put("/{user_id}")
async def update_user(
    user_id: str,
    full_name: Optional[str] = Form(None),
    phone_number: Optional[str] = Form(None),
    status: Optional[str] = Form(None, pattern="^(active|inactive)$"),
    profile_image: UploadFile = File(None),
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    if not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=400, detail="Invalid user id")

    if str(current_user["_id"]) != user_id and current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Forbidden")

    update = {}
    if full_name is not None:
        update["full_name"] = full_name
    if phone_number is not None:
        update["phone_number"] = phone_number
    if status is not None and current_user.get("role") == "admin":
        # hanya admin boleh ubah status
        update["status"] = status

    if profile_image is not None:
        path = await save_upload_file(
            profile_image,
            base_dir=settings.UPLOAD_DIR,
            sub_dir=settings.USER_UPLOAD_SUBDIR,
            prefix=f"user_{user_id}_"
        )
        update["profile_image"] = path

    if not update:
        return {"message": "Nothing to update"}

    update["updated_at"] = datetime.now(timezone.utc)
    res = await db.users.update_one({"_id": ObjectId(user_id)}, {"$set": update})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")

    doc = await db.users.find_one({"_id": ObjectId(user_id)}, {"hashed_password": 0})
    doc["_id"] = str(doc["_id"])
    return {"message": "Updated", "user": doc}



@router.delete("/{user_id}", dependencies=[Depends(require_admin)])
async def delete_user(user_id: str, db=Depends(get_db)):
    if not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=400, detail="Invalid user id")
    res = await db.users.delete_one({"_id": ObjectId(user_id)})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    return {"message": "Deleted"}
