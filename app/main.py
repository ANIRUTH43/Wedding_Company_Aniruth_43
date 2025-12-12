# app/main.py
"""
FastAPI application for multi-tenant organization management with MongoDB.
Supports both shared and dedicated database architectures.
"""

import os
from contextlib import asynccontextmanager
from typing import Dict, Any
from datetime import datetime

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from dotenv import load_dotenv

# Import application modules
from app.routes import router
from app.services import organization_service
from app.logger import get_logger

# Load environment variables
load_dotenv()

# Initialize logger
logger = get_logger(__name__)

# Configuration
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
CORS_ENABLED = os.getenv("CORS_ENABLED", "true").lower() == "true"
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:8000").split(",")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events with improved error handling"""
    logger.info("application_starting", version="1.0.0")
    
    try:
        # Try to ensure database indexes are created
        try:
            await organization_service.ensure_indexes()
            logger.info("database_indexes_ensured")
        except Exception as index_error:
            # Log the error but don't crash the application
            error_msg = str(index_error)[:300]  # Truncate long error messages
            logger.warning(
                "failed_to_create_indexes_on_startup",
                error=error_msg,
                note="Application will continue - indexes will be created on first use"
            )
            logger.info("application_continuing_without_indexes")
            # Application continues - indexes will be created lazily when needed
        
        yield
        
    finally:
        logger.info("application_shutting_down")
        
        # Close database connections
        try:
            await organization_service.close_all_connections()
            logger.info("database_connections_closed")
        except Exception as e:
            logger.error("error_closing_connections", error=str(e))
        
        logger.info("application_shutdown_complete")


# Initialize FastAPI application
app = FastAPI(
    title="Organization Management API",
    description="Multi-tenant organization management system with MongoDB",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)


# CORS Configuration
if CORS_ENABLED:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["*"],
    )
    logger.info("cors_middleware_enabled", allowed_origins=CORS_ORIGINS)


# Request ID Middleware
@app.middleware("http")
async def add_request_id(request: Request, call_next):
    """Add unique request ID to all requests"""
    import uuid
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    
    return response


# Logging Middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all incoming requests and responses"""
    start_time = datetime.utcnow()
    request_id = getattr(request.state, "request_id", "unknown")
    
    logger.info(
        "request_started",
        request_id=request_id,
        method=request.method,
        path=request.url.path,
        client_host=request.client.host if request.client else "unknown"
    )
    
    try:
        response = await call_next(request)
        
        duration = (datetime.utcnow() - start_time).total_seconds()
        
        logger.info(
            "request_completed",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_seconds=round(duration, 3)
        )
        
        return response
        
    except Exception as e:
        duration = (datetime.utcnow() - start_time).total_seconds()
        
        logger.error(
            "request_failed",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            error=str(e),
            duration_seconds=round(duration, 3)
        )
        raise


# Exception Handlers
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Handle HTTP exceptions"""
    request_id = getattr(request.state, "request_id", "unknown")
    
    logger.warning(
        "http_exception",
        request_id=request_id,
        status_code=exc.status_code,
        detail=exc.detail,
        path=request.url.path
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.status_code,
                "message": exc.detail,
                "request_id": request_id,
                "timestamp": datetime.utcnow().isoformat()
            }
        }
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle request validation errors"""
    request_id = getattr(request.state, "request_id", "unknown")
    
    logger.warning(
        "validation_error",
        request_id=request_id,
        errors=exc.errors(),
        path=request.url.path
    )
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": {
                "code": 422,
                "message": "Validation error",
                "details": exc.errors(),
                "request_id": request_id,
                "timestamp": datetime.utcnow().isoformat()
            }
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle all other exceptions"""
    request_id = getattr(request.state, "request_id", "unknown")
    
    logger.error(
        "unhandled_exception",
        request_id=request_id,
        error=str(exc),
        error_type=type(exc).__name__,
        path=request.url.path
    )
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": 500,
                "message": "Internal server error" if ENVIRONMENT == "production" else str(exc),
                "request_id": request_id,
                "timestamp": datetime.utcnow().isoformat()
            }
        }
    )


# Include routers
app.include_router(router, prefix="/api/v1")


# Root endpoints
@app.get("/", tags=["Root"])
async def root() -> Dict[str, Any]:
    """Root endpoint with API information"""
    return {
        "service": "Organization Management API",
        "version": "1.0.0",
        "status": "running",
        "environment": ENVIRONMENT,
        "docs": "/docs",
        "health": "/health",
        "metrics": "/metrics"
    }


@app.get("/health", tags=["Health"])
async def health_check() -> Dict[str, Any]:
    """Health check endpoint with database status"""
    try:
        # Try to get database statistics
        stats = await organization_service.get_statistics()
        db_healthy = True
        db_status = "healthy"
    except Exception as e:
        # Database not available but app is still running
        db_healthy = False
        db_status = "degraded"
        stats = None
        logger.warning("health_check_db_error", error=str(e)[:200])
    
    health_data = {
        "status": "healthy" if db_healthy else "degraded",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().timestamp(),
        "database": {
            "status": db_status,
            "connected": db_healthy
        }
    }
    
    if stats:
        health_data["statistics"] = stats
    
    return health_data


@app.get("/metrics", tags=["Metrics"])
async def metrics() -> Dict[str, Any]:
    """Metrics endpoint for monitoring"""
    try:
        stats = await organization_service.get_statistics()
        return stats
    except Exception as e:
        logger.error("metrics_error", error=str(e))
        return {
            "error": "Unable to retrieve metrics",
            "organizations_total": 0,
            "organizations_shared": 0,
            "organizations_dedicated": 0,
            "database_connections": 0
        }


# Application startup log
logger.info("fastapi_application_initialized")


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=ENVIRONMENT == "development",
        log_level=LOG_LEVEL.lower()
    )
