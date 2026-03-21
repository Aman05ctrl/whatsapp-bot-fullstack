from fastapi import APIRouter, Depends, Query, Header, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from property_backend.app.database import get_db
from property_backend.app.models.property import Property, PropertyImage, PropertyStatus, PropertyType
from property_backend.app.routes import properties
from property_backend.app.schemas.property import PropertyResponse
from property_backend.app.utils.dependencies import get_current_client
from property_backend.app.models.property import Client

router = APIRouter()

BOT_API_TOKEN = "your-bot-secret-token-change-this"


@router.get("/properties/search", response_model=List[PropertyResponse])
def search_properties_for_bot(
    city: Optional[str] = Query(None, description="Filter by city"),
    min_price: Optional[float] = Query(None, ge=0, description="Minimum price"),
    max_price: Optional[float] = Query(None, ge=0, description="Maximum price"),
    bhk: Optional[int] = Query(None, gt=0, le=10, description="Number of BHK"),
    property_type: Optional[PropertyType] = Query(None, description="Property type"),
    limit: int = Query(5, ge=1, le=10, description="Result limit"),
    current_client: Client = Depends(get_current_client),
    db: Session = Depends(get_db)
):
    """
    Search properties for WhatsApp bot
    """
    # Optional: Uncomment to enable token authentication
    # if x_bot_token != BOT_API_TOKEN:
    #     raise HTTPException(
    #         status_code=status.HTTP_401_UNAUTHORIZED,
    #         detail="Invalid bot token"
    #     )
    
    query = db.query(Property).filter(
    Property.status == PropertyStatus.ACTIVE,
    Property.client_id == current_client.id
    )
    
    if city:
        query = query.filter(Property.city.ilike(f"%{city}%"))
    
    if min_price is not None:
        query = query.filter(Property.price >= min_price)
    
    if max_price is not None:
        query = query.filter(Property.price <= max_price)
    
    if bhk is not None:
        query = query.filter(Property.bhk == bhk)
    
    if property_type is not None:
        query = query.filter(Property.property_type == property_type)
    
    properties = query.options(joinedload(Property.images)).limit(limit).all()

    return properties