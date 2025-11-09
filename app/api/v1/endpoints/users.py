import os

from math import ceil

from typing import Optional, Any
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from bson import ObjectId
from datetime import datetime, timezone
from app.db.mongodb_config import get_db
from app.core.config import settings
from app.core.security import create_access_token, verify_password, hash_password, decode_token
from app.api.v1.endpoints.utils import get_current_user, save_upload_file, require_admin, delete_public_upload_safe, encode_mongo

dependencies = [Depends(require_admin)]

router = APIRouter(tags=["Users"])
# router = APIRouter(tags=["Users"], dependencies=None)


@router.get("/me")
async def get_me(
    current_user=Depends(get_current_user),
    db=Depends(get_db)
):
    """
    Ambil data user yang sedang login (dari JWT token).
    """
    user = await db.users.find_one({"_id": current_user["_id"]})

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # jangan expose password
    user.pop("password", None)

    return {"user": encode_mongo(user)}


@router.post("", dependencies=dependencies)
async def create_user(
    email: str = Form(...),
    password: str = Form(...),
    full_name: str | None = Form(None),
    phone_number: str | None = Form(None),
    role: str = Form("user", pattern="^(admin|user)$"),
    status: str = Form("active", pattern="^(active|inactive)$"),
    profile_image: UploadFile | None | str = File(None),
    db=Depends(get_db),
):
    existing = await db.users.find_one({"email": email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already exists")

    # Simpan gambar jika ada
    if isinstance(profile_image, str) and profile_image == "":
        profile_image = None

    image_path = None
    if profile_image is not None and not isinstance(profile_image, str) \
            and profile_image != "" and profile_image.filename:
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


@router.get("", dependencies=dependencies)
async def get_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    search: Optional[str] = Query(None, description="Cari berdasarkan nama/email"),
    role: Optional[str] = Query(None, description="Filter berdasarkan role (admin/user)"),
    status: Optional[str] = Query(None, pattern="^(active|inactive)$"),
    sort_by: Optional[str] = Query("created_at", description="Kolom untuk sorting"),
    order: Optional[str] = Query("desc", description="Urutan: asc atau desc"),
    db=Depends(get_db),
):
    """
    Ambil daftar user dengan pagination, filter, dan sorting.
    """

    query = {}
    if search:
        query["$or"] = [
            {"username": {"$regex": search, "$options": "i"}},
            {"email": {"$regex": search, "$options": "i"}}
        ]
    if role:
        query["role"] = role
    if status:
        query["status"] = status

    # 🔧 Kolom yang diizinkan untuk sorting
    allowed_sort_fields = [
        "username", "email", "role", "status", "created_at", "updated_at"
    ]
    if sort_by not in allowed_sort_fields:
        sort_by = "created_at"

    sort_dir = -1 if order.lower() == "desc" else 1

    total = await db.users.count_documents(query)
    pages = ceil(total / page_size) if total > 0 else 1

    cursor = (
        db.users.find(query)
        .sort(sort_by, sort_dir)
        .skip((page - 1) * page_size)
        .limit(page_size)
    )

    items = []
    async for user in cursor:
        # optional: hapus password field biar aman
        user.pop("password", None)
        items.append(encode_mongo(user))

    return {
        "meta": {
            "page": page,
            "page_size": page_size,
            "pages": pages,
            "total": total,
            "sort_by": sort_by,
            "order": order.lower(),
        },
        "items": items,
    }


@router.get("/{user_id}", dependencies=dependencies)
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


@router.put("/{user_id}", dependencies=dependencies)
async def update_user(
    user_id: str,
    full_name: Optional[str] = Form(None),
    phone_number: Optional[str] = Form(None),
    status: Optional[str] = Form(None, pattern="^(active|inactive|)$"),
    profile_image: UploadFile | None | str = File(None),
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    if not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=400, detail="Invalid user id")

    if str(current_user["_id"]) != user_id and current_user.get(
            "role") != "admin":
        raise HTTPException(status_code=403, detail="Forbidden")

        # Ambil dokumen lama (untuk cleanup gambar lama kalau ganti)
    old = await db.users.find_one({"_id": ObjectId(user_id)},
                                  {"hashed_password": 0})
    if not old:
        raise HTTPException(status_code=404, detail="User not found")

    update = {}
    if full_name is not None:
        update["full_name"] = full_name
    if phone_number is not None:
        update["phone_number"] = phone_number
    if status is not None and current_user.get("role") == "admin":
        update["status"] = status

    if profile_image is not None and not isinstance(profile_image, str) \
            and profile_image != "" and profile_image.filename:
        path = await save_upload_file(
            profile_image,
            base_dir=settings.UPLOAD_DIR,
            sub_dir=settings.USER_UPLOAD_SUBDIR,
            prefix=f"user_{user_id}_"
        )
        update["profile_image"] = path
        delete_public_upload_safe(old.get("profile_image"))

    if not update:
        return {"message": "Nothing to update"}

    update["updated_at"] = datetime.now(timezone.utc)
    res = await db.users.update_one({"_id": ObjectId(user_id)},
                                    {"$set": update})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")

    doc = await db.users.find_one({"_id": ObjectId(user_id)},
                                  {"hashed_password": 0})
    doc["_id"] = str(doc["_id"])
    return {"message": "Updated", "user": doc}



@router.delete("/{user_id}", dependencies=dependencies)
async def delete_user(user_id: str, db=Depends(get_db)):
    if not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=400, detail="Invalid user id")

    # Ambil dulu untuk tahu path fotonya
    doc = await db.users.find_one({"_id": ObjectId(user_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="User not found")

    res = await db.users.delete_one({"_id": ObjectId(user_id)})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="User not found")

    # Bersihkan file foto (jika ada). Gagal hapus = diabaikan.
    delete_public_upload_safe(doc.get("profile_image"))

    return {"message": "Deleted"}
