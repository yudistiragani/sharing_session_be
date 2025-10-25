import os
import uvicorn
import argparse

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager

from app.core.config import settings
from app.api.v1.api import api_router
from app.db.mongodb_config import get_db, init_indexes


@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Startup ---
    db = await get_db()
    await init_indexes(db)
    print("✅ MongoDB indexes initialized.")

    # init folder uploads
    os.makedirs(os.path.join(settings.UPLOAD_DIR, settings.PRODUCT_UPLOAD_SUBDIR), exist_ok=True)
    os.makedirs(os.path.join(settings.UPLOAD_DIR, settings.USER_UPLOAD_SUBDIR), exist_ok=True)
    app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")

    print("✅ Application Folders initialized.")

    app.state.db = db  # bisa panggil db
    yield  # <-- di sini aplikasi berjalan
    app.state.db.client.close()
    # --- Shutdown ---
    # (Kalau mau tutup koneksi Mongo misalnya)
    print("🛑 Application shutting down...")

app = FastAPI(title=settings.PROJECT_NAME, lifespan=lifespan)

# CORS (sesuaikan bila perlu)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static for uploads
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")

# API v1
app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse(url='/docs')
    # return {"message": "OK"}


if __name__ == '__main__':
    argp = argparse.ArgumentParser(description="API GENERAL")
    argp.add_argument("-p", "--port", dest="port", type=int, default=8001)
    argp.add_argument('-w', '--worker', dest='worker', help='api worker', type=int, default=1)
    argp.add_argument('--reload', dest='reload', help='auto reload', action='store_true')
    argp.add_argument('--no-reload', dest='reload', help='non auto reload', action='store_false')
    argp.set_defaults(reload=False)
    args = argp.parse_args()

    uvicorn.run(
        'main:app', host='0.0.0.0', port=args.port, workers=args.worker, reload=args.reload
    )