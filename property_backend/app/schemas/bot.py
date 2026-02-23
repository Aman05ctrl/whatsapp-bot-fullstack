from pydantic import BaseModel, Field
from typing import Optional
from property_backend.app.models.property import PropertyType


class BotPropertySearch(BaseModel):
    """Schema for bot property search"""
    city: Optional[str] = None
    min_price: Optional[float] = Field(None, ge=0)
    max_price: Optional[float] = Field(None, ge=0)
    bhk: Optional[int] = Field(None, gt=0, le=10)
    property_type: Optional[PropertyType] = None


class BotPropertyResponse(BaseModel):
    """Schema for bot property response (simplified)"""
    id: int
    title: str
    city: str
    area: float
    price: float
    emi_available: bool
    emi_amount: Optional[float]
    property_type: PropertyType
    bhk: Optional[int]
    description: Optional[str]
    primary_image: Optional[str] = None
    
    class Config:
        from_attributes = True