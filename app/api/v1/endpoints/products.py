from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from bson import ObjectId
from datetime import datetime, timezone
from app.db.mongodb_config import get_db
from app.core.config import settings
from app.api.v1.endpoints.utils import get_current_user, save_upload_file, require_admin

router = APIRouter(tags=["Products"])

@router.get("")
async def list_products(
    db=Depends(get_db), current_user=Depends(get_current_user),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    search: Optional[str] = Query(None, description="Cari by name/description"),
    category: Optional[str] = Query(None),
    min_price: Optional[float] = Query(None, ge=0),
    max_price: Optional[float] = Query(None, ge=0),
):
    q = {}
    ands = []
    if search:
        ands.append({"$or": [
            {"name": {"$regex": search, "$options": "i"}},
            {"description": {"$regex": search, "$options": "i"}},
        ]})
    if category:
        ands.append({"category": {"$regex": f"^{category}$", "$options": "i"}})
    if min_price is not None:
        ands.append({"price": {"$gte": float(min_price)}})
    if max_price is not None:
        ands.append({"price": {"$lte": float(max_price)}})
    if ands:
        q = {"$and": ands}

    total = await db.products.count_documents(q)
    cursor = db.products.find(q).skip((page - 1) * page_size).limit(page_size).sort("created_at", -1)
    items = []
    async for doc in cursor:
        doc["_id"] = str(doc["_id"])
        items.append(doc)
    pages = (total + page_size - 1) // page_size
    return {"items": items, "meta": {"total": total, "page": page, "page_size": page_size, "pages": pages}}

@router.get("/{product_id}")
async def get_product(product_id: str, db=Depends(get_db), current_user=Depends(get_current_user)):
    if not ObjectId.is_valid(product_id):
        raise HTTPException(status_code=400, detail="Invalid product id")
    doc = await db.products.find_one({"_id": ObjectId(product_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Product not found")
    doc["_id"] = str(doc["_id"])
    return doc

@router.post("", dependencies=[Depends(require_admin)])
async def create_product(
    name: str = Form(...),
    description: Optional[str] = Form(None),
    price: float = Form(...),
    category: Optional[str] = Form(None),
    images: List[UploadFile] = File(default=[]),
    db=Depends(get_db),
):
    saved_images = []
    for img in images:
        path = await save_upload_file(
            img,
            base_dir=settings.UPLOAD_DIR,
            sub_dir=settings.PRODUCT_UPLOAD_SUBDIR,
            prefix="product_"
        )
        saved_images.append(path)

    now = datetime.now(timezone.utc)
    doc = {
        "name": name,
        "description": description,
        "price": float(price),
        "category": category,
        "images": saved_images,
        "created_at": now,
        "updated_at": now
    }
    res = await db.products.insert_one(doc)
    doc["_id"] = str(res.inserted_id)
    return {"message": "Created", "product": doc}

@router.put("/{product_id}", dependencies=[Depends(require_admin)])
async def update_product(
    product_id: str,
    name: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    price: Optional[float] = Form(None),
    category: Optional[str] = Form(None),
    images: List[UploadFile] = File(default=[]),  # replace images if provided
    db=Depends(get_db),
):
    if not ObjectId.is_valid(product_id):
        raise HTTPException(status_code=400, detail="Invalid product id")

    update = {}
    if name is not None: update["name"] = name
    if description is not None: update["description"] = description
    if price is not None: update["price"] = float(price)
    if category is not None: update["category"] = category

    if images:
        saved_images = []
        for img in images:
            path = await save_upload_file(
                img,
                base_dir=settings.UPLOAD_DIR,
                sub_dir=settings.PRODUCT_UPLOAD_SUBDIR,
                prefix=f"product_{product_id}_"
            )
            saved_images.append(path)
        update["images"] = saved_images

    if not update:
        return {"message": "Nothing to update"}

    update["updated_at"] = datetime.now(timezone.utc)
    res = await db.products.update_one({"_id": ObjectId(product_id)}, {"$set": update})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Product not found")

    doc = await db.products.find_one({"_id": ObjectId(product_id)})
    doc["_id"] = str(doc["_id"])
    return {"message": "Updated", "product": doc}

@router.delete("/{product_id}", dependencies=[Depends(require_admin)])
async def delete_product(product_id: str, db=Depends(get_db)):
    if not ObjectId.is_valid(product_id):
        raise HTTPException(status_code=400, detail="Invalid product id")
    res = await db.products.delete_one({"_id": ObjectId(product_id)})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Product not found")
    return {"message": "Deleted"}
