from typing import Optional, Literal
from pydantic import BaseModel, EmailStr, Field
from bson import ObjectId
from datetime import datetime

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

RoleLiteral = Literal["admin", "user"]
StatusLiteral = Literal["active", "inactive"]

class UserBase(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None
    profile_image: Optional[str] = None
    phone_number: Optional[str] = None
    role: RoleLiteral = "user"
    status: StatusLiteral = "active"

class UserCreate(UserBase):
    password: str = Field(min_length=6, max_length=512)

class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    phone_number: Optional[str] = None
    status: Optional[StatusLiteral] = None
    # profile_image diubah via upload file (PUT users/{id}) form-data

class UserInDB(UserBase):
    id: PyObjectId = Field(alias="_id")
    hashed_password: str
    created_at: datetime
    updated_at: datetime

    model_config = {
        "populate_by_name": True,
        "json_encoders": {ObjectId: str, datetime: lambda d: d.isoformat()}
    }

class UserPublic(UserBase):
    id: PyObjectId = Field(alias="_id")
    created_at: datetime
    updated_at: datetime

    model_config = {
        "populate_by_name": True,
        "json_encoders": {ObjectId: str, datetime: lambda d: d.isoformat()}
    }
