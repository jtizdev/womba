"""
Main FastAPI application.
"""

from contextlib import asynccontextmanager
import json

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from loguru import logger
from pathlib import Path

from src.config.settings import settings
from src.api.middleware.jwt_auth import JWTAuthMiddleware

from .routes import stories, test_plans, ui, rag, connect


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    logger.info(f"Starting Womba API Server - Environment: {settings.environment}")
    yield
    logger.info("Shutting down Womba API Server")


# Create FastAPI app
app = FastAPI(
    title="Womba - AI Test Generation Platform",
    description="Generate comprehensive test plans from product stories using AI",
    version="0.1.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add JWT authentication middleware for Atlassian Connect
app.add_middleware(JWTAuthMiddleware)

# Include routers
app.include_router(connect.router, tags=["atlassian-connect"])
app.include_router(stories.router, prefix="/api/v1/stories", tags=["stories"])
app.include_router(test_plans.router, prefix="/api/v1/test-plans", tags=["test-plans"])
app.include_router(ui.router, prefix="/api/v1", tags=["ui"])
app.include_router(rag.router, tags=["rag"])

# Mount static files for web UI
static_path = Path(__file__).parent.parent / "web" / "static"
if static_path.exists():
    app.mount("/static", StaticFiles(directory=str(static_path)), name="static")
    app.mount("/ui", StaticFiles(directory=str(static_path), html=True), name="ui-static")


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "Womba API",
        "version": "0.1.0",
        "status": "operational",
        "docs": "/docs",
        "connect_descriptor": "/atlassian-connect.json"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "environment": settings.environment}


@app.get("/atlassian-connect.json")
async def atlassian_connect_descriptor():
    """
    Serve the Atlassian Connect app descriptor.
    
    This endpoint must be publicly accessible for Jira to install the app.
    """
    try:
        descriptor_path = Path(__file__).parent.parent / "web" / "atlassian-connect.json"
        
        with open(descriptor_path, 'r') as f:
            descriptor = json.load(f)
        
        # Dynamically set baseUrl based on environment
        # In production, this should be your Render URL
        # You can override with WOMBA_BASE_URL env var
        import os
        base_url = os.getenv('WOMBA_BASE_URL', descriptor.get('baseUrl', 'https://womba.onrender.com'))
        descriptor['baseUrl'] = base_url
        
        logger.info(f"Serving Atlassian Connect descriptor with baseUrl: {base_url}")
        
        return JSONResponse(content=descriptor)
        
    except Exception as e:
        logger.error(f"Failed to serve Connect descriptor: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": "Failed to load app descriptor"}
        )

