from pydantic import BaseModel, EmailStr, Field
from typing import Optional

class OrgCreate(BaseModel):
    organization_name: str = Field(..., min_length=1)
    email: EmailStr
    password: str = Field(..., min_length=6)

class OrgOut(BaseModel):
    organization_name: str
    collection_name: str
    admin_email: EmailStr

class AdminLogin(BaseModel):
    email: EmailStr
    password: str

class OrgUpdate(BaseModel):
    organization_name: str
    new_organization_name: Optional[str] = None
    email: Optional[EmailStr] = None
    password: Optional[str] = None
