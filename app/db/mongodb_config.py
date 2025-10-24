from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import settings

_client: AsyncIOMotorClient | None = None

async def get_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(settings.MONGODB_URI)
    return _client

async def get_db():
    client = await get_client()
    return client[settings.MONGODB_DB]

async def init_indexes(db):
    # Users
    await db.users.create_index("email", unique=True)
    await db.users.create_index("status")
    await db.users.create_index("phone_number")  # agar filter phone cepat

    # Revoked tokens TTL
    await db.revoked_tokens.create_index("expiresAt", expireAfterSeconds=0)

    # Products
    await db.products.create_index("name")
    await db.products.create_index("category")
    await db.products.create_index("price")

