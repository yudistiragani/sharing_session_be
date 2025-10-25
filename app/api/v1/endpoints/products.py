import os

from typing import Optional, List, Union, Annotated
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from bson import ObjectId
from datetime import datetime, timezone
from app.db.mongodb_config import get_db
from app.core.config import settings
from app.api.v1.endpoints.utils import get_current_user, save_upload_file, require_admin, normalize_upload_list, encode_mongo

ImagesParam = Annotated[Union[List[UploadFile], List[str]], File()]

router = APIRouter(tags=["Products"])

admin_access = [Depends(require_admin)]
basic_access = [Depends(get_current_user)]

# admin_access = None
# basic_access = None


@router.get("/{product_id}/images", dependencies=basic_access)
async def get_product_images(product_id: str, db=Depends(get_db)):
    """
    Ambil daftar gambar untuk 1 produk (dengan nama, ukuran, dan URL preview).
    """
    if not ObjectId.is_valid(product_id):
        raise HTTPException(status_code=400, detail="Invalid product id")

    product = await db.products.find_one({"_id": ObjectId(product_id)})
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    images = product.get("images", [])
    if not images:
        return {"message": "No images for this product", "images": []}

    image_info_list = []
    for img_path in images:
        # path absolut (buat dapat ukuran file)
        abs_path = os.path.join(settings.BASE_DIR, img_path.lstrip("/"))
        file_name = os.path.basename(img_path)
        size_kb = os.path.getsize(abs_path) / 1024 if os.path.exists(abs_path) else None
        preview_url = f"/uploads/{'/'.join(img_path.split('/')[2:])}" if img_path.startswith("/uploads/") else img_path

        image_info_list.append({
            "file_name": file_name,
            "size_kb": round(size_kb, 2) if size_kb else None,
            "preview_url": preview_url
        })

    return {"message": "OK", "images": image_info_list}

@router.get("", dependencies=basic_access)
async def list_products(
    db=Depends(get_db),
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
        # tambahkan nama kategori
        if doc.get("category_id"):
            cat = await db.categories.find_one({"_id": doc["category_id"]},
                                               {"name": 1})
            doc["category_name"] = cat["name"] if cat else None
        else:
            doc["category_name"] = None

        doc["is_low_stock"] = bool(
            doc.get("stock", 0) <= doc.get("low_stock_threshold", 0))
        items.append(encode_mongo(doc))

    pages = (total + page_size - 1) // page_size
    return {"items": items, "meta": {"total": total, "page": page, "page_size": page_size, "pages": pages}}

@router.get("/{product_id}", dependencies=basic_access)
async def get_product(product_id: str, db=Depends(get_db)):
    if not ObjectId.is_valid(product_id):
        raise HTTPException(status_code=400, detail="Invalid product id")
    doc = await db.products.find_one({"_id": ObjectId(product_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Product not found")
    doc["_id"] = str(doc["_id"])
    if doc.get("category_id"):
        cat = await db.categories.find_one({"_id": doc["category_id"]},
                                           {"name": 1})
        doc["category_name"] = cat["name"] if cat else None
    else:
        doc["category_name"] = None

    doc["is_low_stock"] = bool(
        doc.get("stock", 0) <= doc.get("low_stock_threshold", 0))
    return encode_mongo(doc)

@router.post("", dependencies=admin_access)
async def create_product(
    name: str = Form(...),
    description: Optional[str] = Form(None),
    price: float = Form(...),
    category_id: Optional[str] = Form(None),
    stock: int = Form(0, ge=0),
    low_stock_threshold: int = Form(0, ge=0),
    status: str = Form("active", pattern="^(active|inactive)$"),
    db=Depends(get_db),
):
    cat_obj = None
    if category_id:
        if not ObjectId.is_valid(category_id):
            raise HTTPException(400, "Invalid category id format")
        cat_obj = ObjectId(category_id)
        cat_exist = await db.categories.find_one({"_id": cat_obj, "status": "active"})
        if not cat_exist:
            raise HTTPException(400, "Category not found or inactive")

    now = datetime.now(timezone.utc)
    doc = {
        "name": name,
        "description": description,
        "price": float(price),
        "category_id": cat_obj,
        "images": [],  # kosong dulu
        "stock": int(stock),
        "low_stock_threshold": int(low_stock_threshold),
        "status": status,
        "created_at": now,
        "updated_at": now
    }
    res = await db.products.insert_one(doc)
    created = await db.products.find_one({"_id": res.inserted_id})
    return {"message": "Created", "product": encode_mongo(created)}


@router.post("/{product_id}/images", dependencies=admin_access)
async def upload_product_images(
    product_id: str,
    files: List[UploadFile] = File(...),   # ← required sekarang (File(...))
    replace: bool = Form(False),
    db=Depends(get_db),
):
    # 🔒 validasi ID
    if not ObjectId.is_valid(product_id):
        raise HTTPException(status_code=400, detail="Invalid product id")

    # 🔍 pastikan produk ada
    product = await db.products.find_one({"_id": ObjectId(product_id)})
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    # 🔧 filter file valid
    upload_files = [f for f in files if getattr(f, "filename", None)]
    if not upload_files:
        raise HTTPException(status_code=400, detail="No valid files uploaded")

    # 💾 simpan file ke folder uploads/products
    saved_images = []
    for f in upload_files:
        path = await save_upload_file(
            f,
            base_dir=settings.UPLOAD_DIR,
            sub_dir=settings.PRODUCT_UPLOAD_SUBDIR,
            prefix=f"product_{product_id}_"
        )
        saved_images.append(path)

    # 🔄 update field images
    if replace:
        new_images = saved_images
    else:
        new_images = (product.get("images") or []) + saved_images

    await db.products.update_one(
        {"_id": ObjectId(product_id)},
        {"$set": {"images": new_images, "updated_at": datetime.now(timezone.utc)}}
    )

    # 🔁 ambil ulang produk biar hasil fresh
    doc = await db.products.find_one({"_id": ObjectId(product_id)})
    return {"message": "Images uploaded successfully", "product": encode_mongo(doc)}


@router.put("/{product_id}", dependencies=admin_access)
async def update_product(
    product_id: str,
    name: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    price: Optional[float] = Form(None),
    category_id: Optional[str] = Form(None),
    stock: Optional[int] = Form(None, ge=0),
    low_stock_threshold: Optional[int] = Form(None, ge=0),
    status: Optional[str] = Form(None, pattern="^(active|inactive)$"),
    db=Depends(get_db),
):
    """
    Update data produk (tanpa upload gambar).
    Gambar diatur via endpoint /products/{product_id}/images.
    """

    # 🧩 Validasi ID
    if not ObjectId.is_valid(product_id):
        raise HTTPException(status_code=400, detail="Invalid product id")

    # 🔍 Pastikan produk ada
    product = await db.products.find_one({"_id": ObjectId(product_id)})
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    update = {}

    # 📝 Field-field yang bisa diupdate
    if name is not None:
        update["name"] = name
    if description is not None:
        update["description"] = description
    if price is not None:
        update["price"] = float(price)

    # 🔗 Validasi kategori (jika dikirim)
    if category_id is not None:
        if category_id == "":
            update["category_id"] = None
        else:
            if not ObjectId.is_valid(category_id):
                raise HTTPException(status_code=400, detail="Invalid category id format")
            cat_obj = ObjectId(category_id)
            cat_exist = await db.categories.find_one({"_id": cat_obj, "status": "active"})
            if not cat_exist:
                raise HTTPException(status_code=400, detail="Category not found or inactive")
            update["category_id"] = cat_obj

    if stock is not None:
        update["stock"] = int(stock)
    if low_stock_threshold is not None:
        update["low_stock_threshold"] = int(low_stock_threshold)
    if status is not None:
        update["status"] = status

    if not update:
        return {"message": "Nothing to update"}

    update["updated_at"] = datetime.now(timezone.utc)

    # 💾 Update ke database
    res = await db.products.update_one(
        {"_id": ObjectId(product_id)},
        {"$set": update}
    )

    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Product not found")

    # 🔁 Ambil ulang produk
    doc = await db.products.find_one({"_id": ObjectId(product_id)})

    # tambahkan category_name untuk display
    if doc.get("category_id"):
        cat = await db.categories.find_one({"_id": doc["category_id"]}, {"name": 1})
        doc["category_name"] = cat["name"] if cat else None
    else:
        doc["category_name"] = None

    return {"message": "Product updated successfully", "product": encode_mongo(doc)}


@router.delete("/{product_id}", dependencies=admin_access)
async def delete_product(product_id: str, db=Depends(get_db)):
    """
        Hapus produk dan semua gambar terkait di folder upload.
        """
    if not ObjectId.is_valid(product_id):
        raise HTTPException(status_code=400, detail="Invalid product id")

    product = await db.products.find_one({"_id": ObjectId(product_id)})
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    # 🔥 Hapus semua file fisik
    for img_path in product.get("images", []):
        abs_path = os.path.join(settings.BASE_DIR, img_path.lstrip("/"))
        delete_file_safe(abs_path)

    # 🗑️ Hapus dari database
    await db.products.delete_one({"_id": ObjectId(product_id)})

    return {"message": "Product and images deleted successfully"}


def delete_file_safe(filepath: str):
    """Delete file safely if exists (absolute or relative path)."""
    try:
        if filepath and os.path.exists(filepath):
            os.remove(filepath)
        elif filepath.startswith("/uploads/"):  # relative URL
            abs_path = os.path.join(settings.BASE_DIR, filepath.lstrip("/"))
            if os.path.exists(abs_path):
                os.remove(abs_path)
    except Exception as e:
        print(f"[WARN] Failed to delete file {filepath}: {e}")


@router.delete("/{product_id}/images", dependencies=admin_access)
async def delete_product_images(
    product_id: str,
    filename: Optional[str] = Query(None, description="Nama file yang ingin dihapus. Kosongkan untuk hapus semua."),
    db=Depends(get_db),
):
    """
    Hapus satu gambar (berdasarkan nama file) atau semua gambar produk.
    """
    if not ObjectId.is_valid(product_id):
        raise HTTPException(400, "Invalid product id")

    product = await db.products.find_one({"_id": ObjectId(product_id)})
    if not product:
        raise HTTPException(404, "Product not found")

    images: List[str] = product.get("images") or []
    if not images:
        raise HTTPException(404, "No images found for this product")

    if filename:
        # Hapus 1 file spesifik
        new_images = []
        deleted_files = []
        for img_path in images:
            if img_path.endswith(filename):
                delete_file_safe(os.path.join(settings.BASE_DIR, img_path.lstrip("/")))
                deleted_files.append(img_path)
            else:
                new_images.append(img_path)

        if not deleted_files:
            raise HTTPException(404, f"File '{filename}' not found in product")

        await db.products.update_one(
            {"_id": ObjectId(product_id)},
            {"$set": {"images": new_images}}
        )

        msg = f"Deleted {len(deleted_files)} image(s)"
    else:
        # Hapus semua
        for img_path in images:
            delete_file_safe(os.path.join(settings.BASE_DIR, img_path.lstrip("/")))

        await db.products.update_one(
            {"_id": ObjectId(product_id)},
            {"$set": {"images": []}}
        )
        msg = "All images deleted"

    doc = await db.products.find_one({"_id": ObjectId(product_id)})
    return {"message": msg, "product": encode_mongo(doc)}