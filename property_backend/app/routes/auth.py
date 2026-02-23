from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from property_backend.app.database import get_db
from property_backend.app.models.property import Client
from property_backend.app.schemas.auth import ClientRegister, ClientLogin, Token, ClientResponse
from property_backend.app.utils.auth import hash_password, verify_password, create_access_token
from property_backend.app.utils.dependencies import get_current_client  # ← FIXED: Added this import

router = APIRouter()


@router.post("/register", response_model=ClientResponse, status_code=status.HTTP_201_CREATED)
def register_client(client_data: ClientRegister, db: Session = Depends(get_db)):
    """
    Register a new client (real estate company/agent)
    """
    # Check if email already exists
    existing_client = db.query(Client).filter(Client.email == client_data.email).first()
    
    if existing_client:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create new client
    new_client = Client(
        email=client_data.email,
        password_hash=hash_password(client_data.password),
        company_name=client_data.company_name,
        is_active=True
    )
    
    db.add(new_client)
    db.commit()
    db.refresh(new_client)
    
    return new_client


@router.post("/login", response_model=Token)
def login_client(credentials: ClientLogin, db: Session = Depends(get_db)):
    """
    Login and get JWT access token
    """
    # Get client by email
    client = db.query(Client).filter(Client.email == credentials.email).first()
    
    if not client:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Verify password
    if not verify_password(credentials.password, client.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Check if account is active
    if not client.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive"
        )
    
    # Create access token
    access_token = create_access_token(
        data={"client_id": client.id, "email": client.email}
    )
    
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me", response_model=ClientResponse)
def get_current_client_info(current_client: Client = Depends(get_current_client)):
    """
    Get current authenticated client information
    """
    return current_client