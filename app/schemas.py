# app/schemas.py
"""
Pydantic schemas for request/response validation.
Includes strict validation rules and standardized error responses.
"""
from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
import re


# ============================================================================
# ERROR RESPONSE SCHEMAS
# ============================================================================

class ErrorResponse(BaseModel):
    """Standard error response schema for consistent API error handling."""
    error: str = Field(..., description="Error type/category")
    detail: str = Field(..., description="Detailed error message")
    status_code: int = Field(..., description="HTTP status code")
    timestamp: Optional[str] = Field(default_factory=lambda: datetime.utcnow().isoformat())
    
    class Config:
        json_schema_extra = {
            "example": {
                "error": "ValidationError",
                "detail": "Organization name already exists",
                "status_code": 409,
                "timestamp": "2025-12-12T14:30:00.000Z"
            }
        }


class ValidationErrorDetail(BaseModel):
    """Detailed validation error information."""
    field: str
    message: str
    invalid_value: Optional[Any] = None


class ValidationErrorResponse(BaseModel):
    """Validation error response with field-level details."""
    error: str = "ValidationError"
    detail: str
    status_code: int = 422
    errors: List[ValidationErrorDetail]
    timestamp: Optional[str] = Field(default_factory=lambda: datetime.utcnow().isoformat())


# ============================================================================
# SUCCESS RESPONSE SCHEMAS
# ============================================================================

class SuccessResponse(BaseModel):
    """Standard success response schema."""
    success: bool = True
    message: str
    data: Optional[Dict[str, Any]] = None
    timestamp: Optional[str] = Field(default_factory=lambda: datetime.utcnow().isoformat())
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Organization updated successfully",
                "data": {"organization_name": "Acme Corp"},
                "timestamp": "2025-12-12T14:30:00.000Z"
            }
        }


# ============================================================================
# ORGANIZATION SCHEMAS
# ============================================================================

class OrgCreate(BaseModel):
    """Schema for creating a new organization."""
    organization_name: str = Field(
        ...,
        min_length=3,
        max_length=100,
        description="Organization name (3-100 characters)"
    )
    email: EmailStr = Field(..., description="Admin email address")
    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="Admin password (min 8 chars, must include uppercase, lowercase, and digit)"
    )
    db_uri: Optional[str] = Field(
        None,
        description="Optional: MongoDB connection URI for dedicated database"
    )
    db_name: Optional[str] = Field(
        None,
        min_length=1,
        max_length=64,
        description="Optional: Database name for dedicated database mode"
    )
    
    @validator('organization_name')
    def validate_org_name(cls, v: str) -> str:
        """
        Validate organization name format.
        - Must start with alphanumeric character
        - Can contain letters, numbers, spaces, hyphens, underscores, dots
        - No leading/trailing spaces
        """
        # Check for leading/trailing spaces
        if v.strip() != v:
            raise ValueError('Organization name cannot have leading or trailing spaces')
        
        # Check valid characters
        if not re.match(r'^[a-zA-Z0-9][a-zA-Z0-9\s\-_.]*$', v):
            raise ValueError(
                'Organization name must start with alphanumeric character and '
                'contain only letters, numbers, spaces, hyphens, underscores, or dots'
            )
        
        # Check for consecutive special characters
        if re.search(r'[_\-\.]{2,}', v):
            raise ValueError('Organization name cannot contain consecutive special characters')
        
        # Reserved names
        reserved_names = {'admin', 'root', 'system', 'test', 'master', 'default'}
        if v.lower() in reserved_names:
            raise ValueError(f'Organization name "{v}" is reserved and cannot be used')
        
        return v
    
    @validator('password')
    def validate_password(cls, v: str) -> str:
        """
        Validate password strength.
        Requirements:
        - At least one uppercase letter
        - At least one lowercase letter
        - At least one digit
        - At least one special character (optional but recommended)
        """
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain at least one uppercase letter')
        
        if not any(c.islower() for c in v):
            raise ValueError('Password must contain at least one lowercase letter')
        
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain at least one digit')
        
        # Check for common weak passwords
        weak_passwords = {
            'password', 'password123', '12345678', 'qwerty123',
            'admin123', 'welcome123', 'letmein123'
        }
        if v.lower() in weak_passwords:
            raise ValueError('Password is too weak. Please choose a stronger password')
        
        # Optional: Check for special characters (recommended)
        special_chars = set('!@#$%^&*()_+-=[]{}|;:,.<>?')
        if not any(c in special_chars for c in v):
            # Warning: not enforced but logged
            pass  # Could add warning here
        
        return v
    
    @validator('db_name')
    def validate_db_name(cls, v: Optional[str]) -> Optional[str]:
        """
        Validate database name format.
        - Only alphanumeric characters and underscores allowed
        - Cannot start with a number
        """
        if v is None:
            return v
        
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', v):
            raise ValueError(
                'Database name must start with a letter or underscore and '
                'contain only alphanumeric characters and underscores'
            )
        
        # MongoDB reserved database names
        reserved_db_names = {'admin', 'local', 'config', 'test'}
        if v.lower() in reserved_db_names:
            raise ValueError(f'Database name "{v}" is reserved by MongoDB')
        
        return v
    
    @validator('db_uri')
    def validate_db_uri(cls, v: Optional[str]) -> Optional[str]:
        """Validate MongoDB connection URI format."""
        if v is None:
            return v
        
        # Basic MongoDB URI validation
        if not v.startswith(('mongodb://', 'mongodb+srv://')):
            raise ValueError(
                'Database URI must start with "mongodb://" or "mongodb+srv://"'
            )
        
        # Check for credentials in URI (basic check)
        if '@' not in v and 'localhost' not in v:
            raise ValueError(
                'Database URI should include authentication credentials'
            )
        
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "organization_name": "Acme Corporation",
                "email": "admin@acme.com",
                "password": "SecurePass123!",
                "db_uri": "give your mongodb uri",
                "db_name": "acme_production"
            }
        }


class OrgOut(BaseModel):
    """Schema for organization response data."""
    organization_name: str
    collection_name: str
    admin_email: EmailStr
    db_type: str = Field(..., description="Database type: 'shared' or 'dedicated'")
    db_name: Optional[str] = None
    created_at: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "organization_name": "Acme Corporation",
                "collection_name": "org_acme_corporation",
                "admin_email": "admin@acme.com",
                "db_type": "shared",
                "db_name": "master_db",
                "created_at": "2025-12-12T14:30:00.000Z"
            }
        }


class OrgUpdate(BaseModel):
    """Schema for updating organization details."""
    organization_name: str = Field(
        ...,
        min_length=3,
        max_length=100,
        description="Current organization name"
    )
    new_organization_name: Optional[str] = Field(
        None,
        min_length=3,
        max_length=100,
        description="New organization name (optional)"
    )
    email: Optional[EmailStr] = Field(None, description="New admin email (optional)")
    password: Optional[str] = Field(
        None,
        min_length=8,
        max_length=128,
        description="New admin password (optional)"
    )
    db_uri: Optional[str] = Field(
        None,
        description="New database URI for migration to dedicated mode (optional)"
    )
    db_name: Optional[str] = Field(
        None,
        min_length=1,
        max_length=64,
        description="New database name (optional)"
    )
    
    @validator('new_organization_name')
    def validate_new_org_name(cls, v: Optional[str]) -> Optional[str]:
        """Validate new organization name using same rules as create."""
        if v is None:
            return v
        
        if v.strip() != v:
            raise ValueError('Organization name cannot have leading or trailing spaces')
        
        if not re.match(r'^[a-zA-Z0-9][a-zA-Z0-9\s\-_.]*$', v):
            raise ValueError(
                'Organization name must start with alphanumeric character and '
                'contain only letters, numbers, spaces, hyphens, underscores, or dots'
            )
        
        if re.search(r'[_\-\.]{2,}', v):
            raise ValueError('Organization name cannot contain consecutive special characters')
        
        reserved_names = {'admin', 'root', 'system', 'test', 'master', 'default'}
        if v.lower() in reserved_names:
            raise ValueError(f'Organization name "{v}" is reserved and cannot be used')
        
        return v
    
    @validator('password')
    def validate_password(cls, v: Optional[str]) -> Optional[str]:
        """Validate new password if provided."""
        if v is None:
            return v
        
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain at least one uppercase letter')
        
        if not any(c.islower() for c in v):
            raise ValueError('Password must contain at least one lowercase letter')
        
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain at least one digit')
        
        return v
    
    @validator('db_name')
    def validate_db_name(cls, v: Optional[str]) -> Optional[str]:
        """Validate database name if provided."""
        if v is None:
            return v
        
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', v):
            raise ValueError(
                'Database name must start with a letter or underscore and '
                'contain only alphanumeric characters and underscores'
            )
        
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "organization_name": "Acme Corporation",
                "new_organization_name": "Acme Corp Ltd",
                "email": "newadmin@acme.com",
                "password": "NewSecurePass123!"
            }
        }


# ============================================================================
# AUTHENTICATION SCHEMAS
# ============================================================================

class AdminLogin(BaseModel):
    """Schema for admin login credentials."""
    email: EmailStr = Field(..., description="Admin email address")
    password: str = Field(..., description="Admin password")
    
    class Config:
        json_schema_extra = {
            "example": {
                "email": "admin@acme.com",
                "password": "SecurePass123!"
            }
        }


class TokenResponse(BaseModel):
    """Schema for authentication token response."""
    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: Optional[int] = Field(None, description="Token expiration time in seconds")
    
    class Config:
        json_schema_extra = {
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "bearer",
                "expires_in": 604800
            }
        }


# ============================================================================
# QUERY PARAMETER SCHEMAS
# ============================================================================

class OrgQueryParams(BaseModel):
    """Schema for organization query parameters."""
    organization_name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Organization name to query"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "organization_name": "Acme Corporation"
            }
        }


# ============================================================================
# HEALTH CHECK SCHEMA
# ============================================================================

class HealthCheckResponse(BaseModel):
    """Schema for health check endpoint response."""
    status: str = Field(default="healthy", description="Service health status")
    version: str = Field(..., description="API version")
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    database: Dict[str, Any] = Field(..., description="Database connection status")
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "healthy",
                "version": "1.0.0",
                "timestamp": "2025-12-12T14:30:00.000Z",
                "database": {
                    "connected": True,
                    "collections_count": 5
                }
            }
        }
