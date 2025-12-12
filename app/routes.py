# app/routes.py
"""
API routes for organization management.
Includes authentication, CRUD operations, and proper error handling.
"""
from fastapi import APIRouter, HTTPException, Depends, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from slowapi import Limiter
from slowapi.util import get_remote_address
from typing import Optional

from app.schemas import (
    OrgCreate, OrgOut, AdminLogin, OrgUpdate,
    SuccessResponse, TokenResponse, ErrorResponse
)
from app.services import organization_service
from app import auth
from app.logger import get_logger

logger = get_logger(__name__)

# Initialize router and security
router = APIRouter()
bearer_scheme = HTTPBearer()
limiter = Limiter(key_func=get_remote_address)


# ============================================================================
# AUTHENTICATION & AUTHORIZATION
# ============================================================================

def verify_token(creds: HTTPAuthorizationCredentials = Depends(bearer_scheme)) -> dict:
    """
    Verify JWT token and return payload.
    
    Args:
        creds: HTTP Bearer credentials
        
    Returns:
        Token payload dictionary
        
    Raises:
        HTTPException: If token is invalid or expired
    """
    token = creds.credentials
    payload = auth.decode_token(token)
    
    if not payload:
        logger.warning("invalid_token_attempt")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    logger.debug("token_verified", sub=payload.get("sub"))
    return payload


async def ensure_org_permission(token_payload: dict, org_name: str) -> dict:
    """
    Ensure the token belongs to the specified organization.
    
    Args:
        token_payload: Decoded JWT payload
        org_name: Organization name to verify access
        
    Returns:
        Organization document
        
    Raises:
        HTTPException: If organization not found or access denied
    """
    org = await organization_service.get_organization(org_name)
    
    if not org:
        logger.warning("org_access_denied_not_found", org_name=org_name)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Organization '{org_name}' not found"
        )
    
    token_org_id = token_payload.get("org_id")
    token_email = token_payload.get("sub")
    
    org_id = org["_id"]
    org_admin_email = org["admin"]["email"]
    
    # Verify token matches organization
    if str(token_org_id) != str(org_id) and token_email != org_admin_email:
        logger.warning(
            "org_access_denied_forbidden",
            org_name=org_name,
            token_email=token_email
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: You don't have permission to access this organization"
        )
    
    logger.debug("org_permission_verified", org_name=org_name)
    return org


# ============================================================================
# ORGANIZATION ENDPOINTS
# ============================================================================

@router.post(
    "/org/create",
    response_model=OrgOut,
    status_code=status.HTTP_201_CREATED,
    tags=["Organizations"],
    summary="Create a new organization",
    responses={
        201: {"description": "Organization created successfully"},
        400: {"model": ErrorResponse, "description": "Bad request - validation failed"},
        409: {"model": ErrorResponse, "description": "Conflict - organization already exists"},
        422: {"description": "Validation error"}
    }
)
@limiter.limit("10/minute")
async def create_org(request: Request, payload: OrgCreate):
    """
    Create a new organization with admin account.
    
    **Modes:**
    - **Shared Database** (default): Organization data stored in shared collection
    - **Dedicated Database**: Provide `db_uri` and `db_name` for isolated database
    
    **Requirements:**
    - Organization name: 3-100 characters, alphanumeric with spaces/hyphens/dots
    - Password: Min 8 characters with uppercase, lowercase, and digit
    - Email: Valid email format
    
    **Example:**
    ```
    {
        "organization_name": "Acme Corporation",
        "email": "admin@acme.com",
        "password": "SecurePass123!",
        "db_uri": "mongodb+srv://...",  // Optional
        "db_name": "acme_db"  // Optional
    }
    ```
    """
    try:
        logger.info(
            "create_org_request",
            org_name=payload.organization_name,
            admin_email=payload.email,
            db_type="dedicated" if payload.db_uri else "shared"
        )
        
        result = await organization_service.create_organization(
            org_name=payload.organization_name,
            admin_email=payload.email,
            admin_password=payload.password,
            db_uri=payload.db_uri,
            db_name=payload.db_name
        )
        
        logger.info(
            "org_created_successfully",
            org_name=payload.organization_name,
            org_id=result["id"]
        )
        
        return OrgOut(
            organization_name=result["organization_name"],
            collection_name=result["collection_name"],
            admin_email=result["admin_email"],
            db_type=result["db_type"],
            db_name=result.get("db_name"),
            created_at=result.get("created_at")
        )
        
    except ValueError as e:
        error_msg = str(e)
        logger.warning("org_creation_failed", error=error_msg)
        
        # Determine appropriate status code
        if "already exists" in error_msg or "already registered" in error_msg:
            status_code = status.HTTP_409_CONFLICT
        else:
            status_code = status.HTTP_400_BAD_REQUEST
        
        raise HTTPException(
            status_code=status_code,
            detail=error_msg
        )
    
    except Exception as e:
        logger.error("org_creation_error", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create organization. Please try again later."
        )


@router.get(
    "/org/get",
    response_model=OrgOut,
    tags=["Organizations"],
    summary="Get organization details",
    responses={
        200: {"description": "Organization found"},
        404: {"model": ErrorResponse, "description": "Organization not found"}
    }
)
async def get_org(organization_name: str):
    """
    Retrieve organization details by name.
    
    **Parameters:**
    - `organization_name`: Exact organization name (case-sensitive)
    
    **Returns:** Organization metadata including collection name and database type
    """
    logger.info("get_org_request", org_name=organization_name)
    
    doc = await organization_service.get_organization(organization_name)
    
    if not doc:
        logger.warning("org_not_found", org_name=organization_name)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Organization '{organization_name}' not found"
        )
    
    logger.info("org_retrieved", org_name=organization_name)
    
    return OrgOut(
        organization_name=doc["organization_name"],
        collection_name=doc["collection_name"],
        admin_email=doc["admin"]["email"],
        db_type=doc.get("db_type", "shared"),
        db_name=doc.get("db_name"),
        created_at=doc.get("created_at")
    )


@router.put(
    "/org/update",
    response_model=SuccessResponse,
    tags=["Organizations"],
    summary="Update organization details",
    responses={
        200: {"description": "Organization updated successfully"},
        400: {"model": ErrorResponse, "description": "Bad request"},
        401: {"model": ErrorResponse, "description": "Unauthorized - invalid token"},
        403: {"model": ErrorResponse, "description": "Forbidden - access denied"},
        404: {"model": ErrorResponse, "description": "Organization not found"}
    }
)
async def update_org(
    payload: OrgUpdate,
    token_payload: dict = Depends(verify_token)
):
    """
    Update organization metadata (requires authentication).
    
    **Authentication Required:** Bearer token from admin login
    
    **Updatable Fields:**
    - Organization name (triggers collection rename)
    - Admin email
    - Admin password
    - Database connection details (migration to dedicated mode)
    
    **Note:** Renaming organizations with large datasets (>10K docs) uses background migration.
    
    **Example:**
    ```
    {
        "organization_name": "Acme Corporation",
        "new_organization_name": "Acme Corp Ltd",
        "email": "newadmin@acme.com",
        "password": "NewSecurePass123!"
    }
    ```
    """
    logger.info(
        "update_org_request",
        org_name=payload.organization_name,
        requesting_user=token_payload.get("sub")
    )
    
    # Verify permission
    await ensure_org_permission(token_payload, payload.organization_name)
    
    try:
        await organization_service.update_organization(
            org_name=payload.organization_name,
            new_org_name=payload.new_organization_name,
            email=payload.email,
            password=payload.password,
            db_uri=payload.db_uri,
            db_name=payload.db_name
        )
        
        logger.info(
            "org_updated_successfully",
            org_name=payload.organization_name,
            new_org_name=payload.new_organization_name
        )
        
        return SuccessResponse(
            success=True,
            message="Organization updated successfully",
            data={
                "organization_name": payload.new_organization_name or payload.organization_name
            }
        )
        
    except ValueError as e:
        logger.warning("org_update_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    
    except Exception as e:
        logger.error("org_update_error", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update organization. Please try again later."
        )


@router.delete(
    "/org/delete",
    response_model=SuccessResponse,
    tags=["Organizations"],
    summary="Delete an organization",
    responses={
        200: {"description": "Organization deleted successfully"},
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        403: {"model": ErrorResponse, "description": "Forbidden"},
        404: {"model": ErrorResponse, "description": "Organization not found"}
    }
)
async def delete_org(
    organization_name: str,
    token_payload: dict = Depends(verify_token)
):
    """
    Delete an organization and all associated data (requires authentication).
    
    **Warning:** This action is irreversible. All organization data will be permanently deleted.
    
    **Authentication Required:** Bearer token from admin login
    
    **Deletes:**
    - Organization metadata
    - Organization collection (all tenant data)
    - Database connection cache
    """
    logger.info(
        "delete_org_request",
        org_name=organization_name,
        requesting_user=token_payload.get("sub")
    )
    
    # Verify permission
    await ensure_org_permission(token_payload, organization_name)
    
    success = await organization_service.delete_organization(organization_name)
    
    if not success:
        logger.warning("org_delete_failed_not_found", org_name=organization_name)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Organization '{organization_name}' not found"
        )
    
    logger.info("org_deleted_successfully", org_name=organization_name)
    
    return SuccessResponse(
        success=True,
        message=f"Organization '{organization_name}' deleted successfully",
        data={"organization_name": organization_name}
    )


# ============================================================================
# AUTHENTICATION ENDPOINTS
# ============================================================================

@router.post(
    "/admin/login",
    response_model=TokenResponse,
    tags=["Authentication"],
    summary="Admin login",
    responses={
        200: {"description": "Login successful"},
        401: {"model": ErrorResponse, "description": "Invalid credentials"},
        429: {"description": "Too many requests - rate limit exceeded"}
    }
)
@limiter.limit("5/minute")
async def admin_login(request: Request, payload: AdminLogin):
    """
    Authenticate admin and receive JWT access token.
    
    **Rate Limited:** 5 requests per minute per IP address
    
    **Returns:** JWT token valid for 7 days (default)
    
    **Example:**
    ```
    {
        "email": "admin@acme.com",
        "password": "SecurePass123!"
    }
    ```
    
    **Response:**
    ```
    {
        "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
        "token_type": "bearer",
        "expires_in": 604800
    }
    ```
    """
    logger.info("admin_login_attempt", email=payload.email)
    
    authres = await organization_service.authenticate_admin(
        email=payload.email,
        password=payload.password
    )
    
    if not authres:
        logger.warning("login_failed_invalid_credentials", email=payload.email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    # Create access token
    token = auth.create_access_token({
        "sub": authres["admin_email"],
        "org_id": authres["org_id"],
        "org_name": authres["org_name"]
    })
    
    logger.info(
        "login_successful",
        email=payload.email,
        org_name=authres["org_name"]
    )
    
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=auth.ACCESS_TOKEN_EXPIRE_MINUTES * 60  # Convert to seconds
    )


@router.post(
    "/admin/verify",
    tags=["Authentication"],
    summary="Verify token validity",
    responses={
        200: {"description": "Token is valid"},
        401: {"model": ErrorResponse, "description": "Invalid or expired token"}
    }
)
async def verify_admin_token(token_payload: dict = Depends(verify_token)):
    """
    Verify if the provided JWT token is valid.
    
    **Authentication Required:** Bearer token
    
    **Returns:** Token payload information
    """
    return {
        "valid": True,
        "admin_email": token_payload.get("sub"),
        "org_id": token_payload.get("org_id"),
        "org_name": token_payload.get("org_name")
    }
