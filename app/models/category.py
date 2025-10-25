from pydantic import BaseModel, Field
from bson import ObjectId
from datetime import datetime
from typing import Optional, Literal

class PyObjectId(ObjectId):
    @classmethod
    def __get_pydantic_core_schema__(cls, _source, _handler):
        from pydantic_core import core_schema
        def validate(v):
            if isinstance(v, ObjectId):
                return v
            if not ObjectId.is_valid(v):
                raise ValueError("Invalid ObjectId")
            return ObjectId(v)
        return core_schema.no_info_after_validator_function(validate, core_schema.str_schema())

CategoryStatus = Literal["active", "inactive"]

class CategoryBase(BaseModel):
    name: str
    slug: Optional[str] = None
    status: CategoryStatus = "active"

class CategoryCreate(CategoryBase):
    pass

class CategoryUpdate(BaseModel):
    name: Optional[str] = None
    slug: Optional[str] = None
    status: Optional[CategoryStatus] = None

class CategoryInDB(CategoryBase):
    id: PyObjectId = Field(alias="_id")
    created_at: datetime
    updated_at: datetime

    model_config = {
        "populate_by_name": True,
        "json_encoders": {ObjectId: str, datetime: lambda d: d.isoformat()}
    }

class CategoryPublic(CategoryBase):
    id: PyObjectId = Field(alias="_id")
    created_at: datetime
    updated_at: datetime

    model_config = {
        "populate_by_name": True,
        "json_encoders": {ObjectId: str, datetime: lambda d: d.isoformat()}
    }
