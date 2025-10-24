import os
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseModel):
    PROJECT_NAME: str = "FastAPI Mongo API"
    API_V1_STR: str = "/api/v1"
    MONGODB_URI: str = os.getenv("MONGODB_URI", "mongodb+srv://agantemppassword123:IniPasswordAdm1n@pms.34fgkqt.mongodb.net/admin")
    MONGODB_DB: str = os.getenv("MONGODB_DB", "pms")

    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "super-secret-key-change-me")
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))

    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "uploads")
    USER_UPLOAD_SUBDIR: str = "users"
    PRODUCT_UPLOAD_SUBDIR: str = "products"

settings = Settings()
