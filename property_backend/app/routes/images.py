from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from typing import List
from property_backend.app.database import get_db
from property_backend.app.models.property import Client, Property, PropertyImage
from property_backend.app.schemas.property import PropertyImageResponse
from property_backend.app.utils.dependencies import get_current_client
from property_backend.app.utils.storage import storage

router = APIRouter()

MAX_IMAGES_PER_PROPERTY = 10
ALLOWED_EXTENSIONS = ["jpg", "jpeg", "png", "webp"]
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB in bytes


@router.post("/{property_id}/images", response_model=List[PropertyImageResponse], status_code=status.HTTP_201_CREATED)
async def upload_property_images(
    property_id: int,
    files: List[UploadFile] = File(...),
    current_client: Client = Depends(get_current_client),
    db: Session = Depends(get_db)
):
    """
    Upload images for a property
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
    
    current_image_count = db.query(PropertyImage).filter(
        PropertyImage.property_id == property_id
    ).count()
    
    if current_image_count + len(files) > MAX_IMAGES_PER_PROPERTY:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Maximum {MAX_IMAGES_PER_PROPERTY} images allowed per property"
        )
    
    uploaded_images = []
    
    for file in files:
        file_extension = file.filename.split(".")[-1].lower()
        
        if file_extension not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid file type. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
            )
        
        file_content = await file.read()

        # Check file size
        if len(file_content) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File size too large. Maximum allowed is {MAX_FILE_SIZE // (1024 * 1024)}MB"
            )
        
        image_url = storage.upload_file(file_content, file_extension)
        
        if not image_url:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to upload image"
            )
        
        is_primary = current_image_count == 0 and len(uploaded_images) == 0
        
        new_image = PropertyImage(
            property_id=property_id,
            image_url=image_url,
            is_primary=is_primary
        )
        
        db.add(new_image)
        uploaded_images.append(new_image)
    
    db.commit()
    
    for img in uploaded_images:
        db.refresh(img)
    
    return uploaded_images


@router.get("/{property_id}/images", response_model=List[PropertyImageResponse])
def get_property_images(
    property_id: int,
    current_client: Client = Depends(get_current_client),
    db: Session = Depends(get_db)
):
    """
    Get all images for a property
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
    
    images = db.query(PropertyImage).filter(
        PropertyImage.property_id == property_id
    ).all()
    
    return images


@router.patch("/{property_id}/images/{image_id}/primary", response_model=PropertyImageResponse)
def set_primary_image(
    property_id: int,
    image_id: int,
    current_client: Client = Depends(get_current_client),
    db: Session = Depends(get_db)
):
    """
    Set an image as primary
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
    
    image = db.query(PropertyImage).filter(
        PropertyImage.id == image_id,
        PropertyImage.property_id == property_id
    ).first()
    
    if not image:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Image not found"
        )
    
    db.query(PropertyImage).filter(
        PropertyImage.property_id == property_id
    ).update({"is_primary": False})
    
    image.is_primary = True
    
    db.commit()
    db.refresh(image)
    
    return image


@router.delete("/{property_id}/images/{image_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_property_image(
    property_id: int,
    image_id: int,
    current_client: Client = Depends(get_current_client),
    db: Session = Depends(get_db)
):
    """
    Delete a property image
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
    
    image = db.query(PropertyImage).filter(
        PropertyImage.id == image_id,
        PropertyImage.property_id == property_id
    ).first()
    
    if not image:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Image not found"
        )
    
    storage.delete_file(image.image_url)
    
    db.delete(image)
    db.commit()
    
    return None