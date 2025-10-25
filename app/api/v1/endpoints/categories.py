from fastapi import APIRouter, Depends, HTTPException, Body, Query
from datetime import datetime, timezone
from bson import ObjectId
from typing import Optional
from app.db.mongodb_config import get_db
from app.api.v1.endpoints.utils import get_current_user, require_admin

router = APIRouter(tags=["Categories"], prefix="/categories")

# =====================
# 🟩 Get all categories (with pagination & filter)
# =====================
@router.get("")
async def list_categories(
    db=Depends(get_db),
    q: Optional[str] = Query(None, description="Cari by name/slug"),
    status: Optional[str] = Query(None, pattern="^(active|inactive)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    current_user=Depends(get_current_user),
):
    cond = {}
    ands = []
    if q:
        ands.append({
            "$or": [
                {"name": {"$regex": q, "$options": "i"}},
                {"slug": {"$regex": q, "$options": "i"}}
            ]
        })
    if status:
        ands.append({"status": status})
    if ands:
        cond = {"$and": ands}

    total = await db.categories.count_documents(cond)
    cursor = (
        db.categories.find(cond)
        .skip((page - 1) * page_size)
        .limit(page_size)
        .sort("created_at", -1)
    )

    items = []
    async for d in cursor:
        d["_id"] = str(d["_id"])
        items.append(d)

    pages = (total + page_size - 1) // page_size
    return {
        "items": items,
        "meta": {
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": pages
        }
    }

# =====================
# 🟩 Simple Select list (for dropdowns)
# =====================
@router.get("/select")
async def select_categories(
    db=Depends(get_db),
    status: Optional[str] = Query("active", pattern="^(active|inactive)$")
):
    cond = {"status": status}
    cursor = db.categories.find(cond, {"name": 1})
    items = []
    async for cat in cursor:
        items.append({"id": str(cat["_id"]), "name": cat["name"]})
    return items

# =====================
# 🟨 Get single category detail
# =====================
@router.get("/{category_id}")
async def get_category(category_id: str, db=Depends(get_db)):
    if not ObjectId.is_valid(category_id):
        raise HTTPException(400, "Invalid category id")
    cat = await db.categories.find_one({"_id": ObjectId(category_id)})
    if not cat:
        raise HTTPException(404, "Category not found")
    cat["_id"] = str(cat["_id"])
    return cat

# =====================
# 🟦 Create new category
# =====================
@router.post("", dependencies=[Depends(require_admin)])
async def create_category(
    name: str = Body(...),
    slug: Optional[str] = Body(None),
    status: str = Body("active", pattern="^(active|inactive)$"),
    db=Depends(get_db),
):
    exist = await db.categories.find_one({"name": name})
    if exist:
        raise HTTPException(400, "Category name already exists")

    now = datetime.now(timezone.utc)
    doc = {
        "name": name,
        "slug": slug,
        "status": status,
        "created_at": now,
        "updated_at": now
    }
    res = await db.categories.insert_one(doc)
    doc["_id"] = str(res.inserted_id)
    return {"message": "Created", "category": doc}

# =====================
# 🟧 Update category
# =====================
@router.put("/{category_id}", dependencies=[Depends(require_admin)])
async def update_category(
    category_id: str,
    name: Optional[str] = Body(None),
    slug: Optional[str] = Body(None),
    status: Optional[str] = Body(None),
    db=Depends(get_db),
):
    if not ObjectId.is_valid(category_id):
        raise HTTPException(400, "Invalid id")

    update = {}
    if name is not None:
        update["name"] = name
    if slug is not None:
        update["slug"] = slug
    if status is not None:
        update["status"] = status
    if not update:
        return {"message": "Nothing to update"}

    update["updated_at"] = datetime.now(timezone.utc)
    res = await db.categories.update_one({"_id": ObjectId(category_id)}, {"$set": update})
    if res.matched_count == 0:
        raise HTTPException(404, "Category not found")

    doc = await db.categories.find_one({"_id": ObjectId(category_id)})
    doc["_id"] = str(doc["_id"])
    return {"message": "Updated", "category": doc}

# =====================
# 🟥 Delete category
# =====================
@router.delete("/{category_id}", dependencies=[Depends(require_admin)])
async def delete_category(category_id: str, db=Depends(get_db)):
    if not ObjectId.is_valid(category_id):
        raise HTTPException(400, "Invalid id")

    # Cek apakah masih digunakan oleh produk
    used = await db.products.find_one({"category_id": ObjectId(category_id)})
    if used:
        raise HTTPException(400, "Cannot delete category; still used by products.")

    res = await db.categories.delete_one({"_id": ObjectId(category_id)})
    if res.deleted_count == 0:
        raise HTTPException(404, "Category not found")

    return {"message": "Deleted successfully"}
