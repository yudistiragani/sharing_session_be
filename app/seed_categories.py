import asyncio
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient

async def seed_categories():
    client = AsyncIOMotorClient("mongodb+srv://agantemppassword123:IniPasswordAdm1n@pms.34fgkqt.mongodb.net/admin")
    db = client["pms"]

    data = [
        {"name": "Meja", "status": "active"},
        {"name": "Sofa", "status": "active"},
        {"name": "Kursi", "status": "active"},
        {"name": "Rak", "status": "inactive"},
        {"name": "Lemari", "status": "active"},
        {"name": "Lampu", "status": "active"},
    ]

    now = datetime.now(timezone.utc)
    for d in data:
        d["created_at"] = now
        d["updated_at"] = now

    await db.categories.insert_many(data)
    print("✅ Seed categories inserted successfully")

if __name__ == "__main__":
    asyncio.run(seed_categories())
