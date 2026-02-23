from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Optional
from property_backend.app.database import get_db
from property_backend.app.models.property import Client, Property, PropertyStatus
from property_backend.app.schemas.property import (
    PropertyCreate, 
    PropertyUpdate, 
    PropertyResponse, 
    PropertyListResponse
)
from property_backend.app.utils.dependencies import get_current_client

router = APIRouter()


@router.post("/", response_model=PropertyResponse, status_code=status.HTTP_201_CREATED)
def create_property(
    property_data: PropertyCreate,
    current_client: Client = Depends(get_current_client),
    db: Session = Depends(get_db)
):
    """
    Create a new property
    """
    new_property = Property(
        client_id=current_client.id,
        **property_data.model_dump()
    )
    
    db.add(new_property)
    db.commit()
    db.refresh(new_property)
    
    return new_property


@router.get("/", response_model=PropertyListResponse)
def get_all_properties(
    current_client: Client = Depends(get_current_client),
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    status_filter: Optional[PropertyStatus] = None
):
    """
    Get all properties for the authenticated client
    """
    query = db.query(Property).filter(
        Property.client_id == current_client.id,
        Property.status != PropertyStatus.INACTIVE
    )
    
    if status_filter:
        query = query.filter(Property.status == status_filter)
    
    total = query.count()
    properties = query.offset(skip).limit(limit).all()
    
    return {
        "total": total,
        "properties": properties
    }


@router.get("/{property_id}", response_model=PropertyResponse)
def get_property_by_id(
    property_id: int,
    current_client: Client = Depends(get_current_client),
    db: Session = Depends(get_db)
):
    """
    Get a specific property by ID
    """
    property_obj = db.query(Property).filter(
        Property.id == property_id,
        Property.client_id == current_client.id
    ).first()
    
    if not property_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Property not found"
        )
    
    return property_obj


@router.put("/{property_id}", response_model=PropertyResponse)
def update_property(
    property_id: int,
    property_data: PropertyUpdate,
    current_client: Client = Depends(get_current_client),
    db: Session = Depends(get_db)
):
    """
    Update a property
    """
    property_obj = db.query(Property).filter(
        Property.id == property_id,
        Property.client_id == current_client.id
    ).first()
    
    if not property_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Property not found"
        )
    
    update_data = property_data.model_dump(exclude_unset=True)
    
    for key, value in update_data.items():
        setattr(property_obj, key, value)
    
    db.commit()
    db.refresh(property_obj)
    
    return property_obj


@router.patch("/{property_id}/sold", response_model=PropertyResponse)
def mark_property_as_sold(
    property_id: int,
    current_client: Client = Depends(get_current_client),
    db: Session = Depends(get_db)
):
    """
    Mark a property as sold
    """
    property_obj = db.query(Property).filter(
        Property.id == property_id,
        Property.client_id == current_client.id
    ).first()
    
    if not property_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Property not found"
        )
    
    property_obj.status = PropertyStatus.SOLD
    
    db.commit()
    db.refresh(property_obj)
    
    return property_obj


@router.delete("/{property_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_property(
    property_id: int,
    current_client: Client = Depends(get_current_client),
    db: Session = Depends(get_db)
):
    """
    Soft delete a property (mark as inactive) and delete all images from Cloudinary
    """
    from property_backend.app.models.property import PropertyImage
    from property_backend.app.utils.storage import storage

    property_obj = db.query(Property).filter(
        Property.id == property_id,
        Property.client_id == current_client.id
    ).first()
    
    if not property_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Property not found"
        )
    
    # Delete all images from Cloudinary
    images = db.query(PropertyImage).filter(
        PropertyImage.property_id == property_id
    ).all()
    
    for image in images:
        storage.delete_file(image.image_url)
        db.delete(image)
    
    # Mark property as inactive
    property_obj.status = PropertyStatus.INACTIVE
    
    db.commit()
    
    return None