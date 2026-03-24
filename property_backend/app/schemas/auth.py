from pydantic import BaseModel, EmailStr, Field
from typing import Optional


class ClientRegister(BaseModel):
    """Schema for client registration"""
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=100)
    company_name: str = Field(..., min_length=2, max_length=255)


class ClientLogin(BaseModel):
    """Schema for client login"""
    email: EmailStr
    password: str


class Token(BaseModel):
    """Schema for token response"""
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    """Schema for token payload data"""
    email: Optional[str] = None
    client_id: Optional[int] = None


class ClientResponse(BaseModel):
    """Schema for client response"""
    id: int
    email: str
    company_name: str
    is_active: bool
    
    class Config:
        from_attributes = True