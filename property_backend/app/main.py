from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from property_backend.app.config import settings
from property_backend.app.database import engine, Base

# Import models to register them with Base
from property_backend.app.models import property  # noqa: F401

# Import routers
from property_backend.app.routes import auth, properties, images, bot

# Create database tables
Base.metadata.create_all(bind=engine)

# Initialize FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    description="Real Estate Property Management Backend",
    version="1.0.0",
    debug=settings.DEBUG
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {"status": "running", "message": "Real Estate Property Backend API"}


@app.get("/health")
def health():
    return {"status": "healthy", "database": "connected"}


# Include routers (ORDER MATTERS)
app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
app.include_router(properties.router, prefix="/api/properties", tags=["Properties"])
app.include_router(images.router, prefix="/api/properties", tags=["Images"])
app.include_router(bot.router, prefix="/api/bot", tags=["Bot"])