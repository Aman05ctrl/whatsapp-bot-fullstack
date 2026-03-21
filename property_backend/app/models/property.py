from sqlalchemy import Column, Integer, String, Boolean, Float, DateTime, ForeignKey, Enum, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
import enum
from property_backend.app.database import Base


class PropertyStatus(str, enum.Enum):
    """Property status enumeration"""
    ACTIVE = "active"
    SOLD = "sold"
    INACTIVE = "inactive"


class PropertyType(str, enum.Enum):
    """Property type enumeration"""
    APARTMENT = "apartment"
    VILLA = "villa"
    PLOT = "plot"
    COMMERCIAL = "commercial"
    FARMHOUSE = "farmhouse"
    OTHER = "other"


class Client(Base):
    """
    Client model - Real estate companies/agents
    """
    __tablename__ = "clients"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    company_name = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationship
    properties = relationship("Property", back_populates="client", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Client(id={self.id}, email={self.email}, company={self.company_name})>"


class Property(Base):
    """
    Property model - Real estate listings
    """
    __tablename__ = "properties"
    
    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Property details
    title = Column(String(255), nullable=False, index=True)
    city = Column(String(100), nullable=False, index=True)
    area = Column(Float, nullable=False)  # in sq ft
    price = Column(Float, nullable=False, index=True)
    
    # EMI details
    emi_available = Column(Boolean, default=False, nullable=False)
    emi_amount = Column(Float, nullable=True)
    
    # Investment details
    expected_roi = Column(Float, nullable=True)  # in percentage
    
    # Property specifications
    property_type = Column(Enum(PropertyType), nullable=False, index=True)
    bhk = Column(Integer, nullable=True)  # Null for plots/commercial
    description = Column(Text, nullable=True)
    
    # Status tracking
    status = Column(Enum(PropertyStatus), default=PropertyStatus.ACTIVE, nullable=False, index=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    client = relationship("Client", back_populates="properties")
    images = relationship("PropertyImage", back_populates="property", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Property(id={self.id}, title={self.title}, city={self.city}, status={self.status})>"


class PropertyImage(Base):
    """
    PropertyImage model - Images for properties
    """
    __tablename__ = "property_images"
    
    id = Column(Integer, primary_key=True, index=True)
    property_id = Column(Integer, ForeignKey("properties.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Image details
    image_url = Column(String(500), nullable=False)
    is_primary = Column(Boolean, default=False, nullable=False)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Relationship
    property = relationship("Property", back_populates="images")
    
    def __repr__(self):
        return f"<PropertyImage(id={self.id}, property_id={self.property_id}, is_primary={self.is_primary})>"