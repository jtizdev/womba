"""
Main FastAPI application.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from loguru import logger
from pathlib import Path

from src.config.settings import settings

from .routes import stories, test_plans, ui, rag


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

# Include routers
app.include_router(stories.router, prefix="/api/v1/stories", tags=["stories"])
app.include_router(test_plans.router, prefix="/api/v1/test-plans", tags=["test-plans"])
app.include_router(ui.router, prefix="/api/v1", tags=["ui"])
app.include_router(rag.router, tags=["rag"])

# Mount static files for web UI
static_path = Path(__file__).parent.parent / "web" / "static"
if static_path.exists():
    app.mount("/ui", StaticFiles(directory=str(static_path), html=True), name="static")


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "Womba API",
        "version": "0.1.0",
        "status": "operational",
        "docs": "/docs",
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "environment": settings.environment}

