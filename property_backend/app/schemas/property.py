from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from property_backend.app.models.property import PropertyStatus, PropertyType


class PropertyImageResponse(BaseModel):
    """Schema for property image response"""
    id: int
    image_url: str
    is_primary: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


class PropertyCreate(BaseModel):
    """Schema for creating a property"""
    title: str = Field(..., min_length=5, max_length=255)
    city: str = Field(..., min_length=2, max_length=100)
    area: float = Field(..., gt=0)
    price: float = Field(..., gt=0)
    emi_available: bool = False
    emi_amount: Optional[float] = Field(None, gt=0)
    expected_roi: Optional[float] = Field(None, ge=0, le=100)
    property_type: PropertyType
    bhk: Optional[int] = Field(None, gt=0, le=10)
    bedrooms: Optional[int] = Field(None, ge=0)
    bathrooms: Optional[float] = Field(None, ge=0)
    address: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    kitchen: Optional[int] = None
    dining_hall: Optional[int] = None
    hall: Optional[int] = None
    terrace: Optional[bool] = None
    description: Optional[str] = None
    status: PropertyStatus = PropertyStatus.ACTIVE
    currency: str = 'AED'


class PropertyUpdate(BaseModel):
    """Schema for updating a property"""
    title: Optional[str] = Field(None, min_length=5, max_length=255)
    city: Optional[str] = Field(None, min_length=2, max_length=100)
    area: Optional[float] = Field(None, gt=0)
    price: Optional[float] = Field(None, gt=0)
    emi_available: Optional[bool] = None
    emi_amount: Optional[float] = Field(None, gt=0)
    expected_roi: Optional[float] = Field(None, ge=0, le=100)
    property_type: Optional[PropertyType] = None
    bhk: Optional[int] = Field(None, gt=0, le=10)
    bedrooms: Optional[int] = Field(None, ge=0)
    bathrooms: Optional[float] = Field(None, ge=0)
    address: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    kitchen: Optional[int] = None
    dining_hall: Optional[int] = None
    hall: Optional[int] = None
    terrace: Optional[bool] = None
    description: Optional[str] = None
    status: Optional[PropertyStatus] = None
    currency: Optional[str] = None


class PropertyResponse(BaseModel):
    """Schema for property response"""
    id: int
    client_id: int
    title: str
    city: str
    area: float
    price: float
    emi_available: bool
    emi_amount: Optional[float]
    expected_roi: Optional[float]
    property_type: PropertyType
    bhk: Optional[int]
    bedrooms: Optional[int] = None
    bathrooms: Optional[float]
    address: Optional[str]
    state: Optional[str]
    zip_code: Optional[str]
    kitchen: Optional[int] = None
    dining_hall: Optional[int] = None
    hall: Optional[int] = None
    terrace: Optional[bool] = None
    description: Optional[str]
    status: PropertyStatus
    currency: str = 'AED'
    created_at: datetime
    updated_at: datetime
    images: List[PropertyImageResponse] = []
    
    class Config:
        from_attributes = True


class PropertyListResponse(BaseModel):
    """Schema for property list response"""
    total: int
    properties: List[PropertyResponse]