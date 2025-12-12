# tests/test_organizations.py
"""
Comprehensive test suite for organization management API.
Tests all endpoints including positive and negative cases.
"""
import pytest
import asyncio
from httpx import AsyncClient
from motor.motor_asyncio import AsyncIOMotorClient
from app.main import app
from app.db import master_db
from app.services import organization_service
import os
from dotenv import load_dotenv

load_dotenv()

# Test configuration
TEST_DB_URI = os.getenv("MONGO_URI")
TEST_ORG_NAME = "Test Organization"
TEST_ADMIN_EMAIL = "test@example.com"
TEST_ADMIN_PASSWORD = "TestPass123!"


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
async def client():
    """Create async HTTP client for testing."""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


@pytest.fixture(scope="function")
async def cleanup_test_orgs():
    """Cleanup test organizations before and after tests."""
    # Cleanup before test
    await master_db["organizations"].delete_many({"organization_name": {"$regex": "^Test"}})
    
    yield
    
    # Cleanup after test
    await master_db["organizations"].delete_many({"organization_name": {"$regex": "^Test"}})


@pytest.fixture
async def created_org(client, cleanup_test_orgs):
    """Create a test organization and return its data."""
    response = await client.post(
        "/api/v1/org/create",
        json={
            "organization_name": TEST_ORG_NAME,
            "email": TEST_ADMIN_EMAIL,
            "password": TEST_ADMIN_PASSWORD
        }
    )
    assert response.status_code == 201
    return response.json()


@pytest.fixture
async def admin_token(client, created_org):
    """Get admin authentication token."""
    response = await client.post(
        "/api/v1/admin/login",
        json={
            "email": TEST_ADMIN_EMAIL,
            "password": TEST_ADMIN_PASSWORD
        }
    )
    assert response.status_code == 200
    data = response.json()
    return data["access_token"]


# ============================================================================
# HEALTH CHECK TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_root_endpoint(client):
    """Test root endpoint returns API information."""
    response = await client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "Organization Management API"
    assert data["version"] == "1.0.0"
    assert data["status"] == "running"


@pytest.mark.asyncio
async def test_health_check(client):
    """Test health check endpoint."""
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["database"]["connected"] is True


# ============================================================================
# ORGANIZATION CREATE TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_create_organization_success(client, cleanup_test_orgs):
    """Test successful organization creation."""
    response = await client.post(
        "/api/v1/org/create",
        json={
            "organization_name": TEST_ORG_NAME,
            "email": TEST_ADMIN_EMAIL,
            "password": TEST_ADMIN_PASSWORD
        }
    )
    
    assert response.status_code == 201
    data = response.json()
    assert data["organization_name"] == TEST_ORG_NAME
    assert data["admin_email"] == TEST_ADMIN_EMAIL
    assert data["db_type"] == "shared"
    assert "collection_name" in data
    assert "created_at" in data


@pytest.mark.asyncio
async def test_create_organization_duplicate_name(client, created_org):
    """Test creating organization with duplicate name returns 409."""
    response = await client.post(
        "/api/v1/org/create",
        json={
            "organization_name": TEST_ORG_NAME,
            "email": "another@example.com",
            "password": TEST_ADMIN_PASSWORD
        }
    )
    
    assert response.status_code == 409
    data = response.json()
    assert "already exists" in data["detail"]


@pytest.mark.asyncio
async def test_create_organization_duplicate_email(client, created_org):
    """Test creating organization with duplicate admin email returns 409."""
    response = await client.post(
        "/api/v1/org/create",
        json={
            "organization_name": "Another Test Org",
            "email": TEST_ADMIN_EMAIL,
            "password": TEST_ADMIN_PASSWORD
        }
    )
    
    assert response.status_code == 409
    data = response.json()
    assert "already registered" in data["detail"]


@pytest.mark.asyncio
async def test_create_organization_invalid_name(client, cleanup_test_orgs):
    """Test creating organization with invalid name returns 422."""
    response = await client.post(
        "/api/v1/org/create",
        json={
            "organization_name": "ab",  # Too short
            "email": TEST_ADMIN_EMAIL,
            "password": TEST_ADMIN_PASSWORD
        }
    )
    
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_organization_weak_password(client, cleanup_test_orgs):
    """Test creating organization with weak password returns 422."""
    response = await client.post(
        "/api/v1/org/create",
        json={
            "organization_name": TEST_ORG_NAME,
            "email": TEST_ADMIN_EMAIL,
            "password": "weak"  # Too short, no uppercase, no digit
        }
    )
    
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_organization_invalid_email(client, cleanup_test_orgs):
    """Test creating organization with invalid email returns 422."""
    response = await client.post(
        "/api/v1/org/create",
        json={
            "organization_name": TEST_ORG_NAME,
            "email": "not-an-email",
            "password": TEST_ADMIN_PASSWORD
        }
    )
    
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_organization_reserved_name(client, cleanup_test_orgs):
    """Test creating organization with reserved name returns 422."""
    response = await client.post(
        "/api/v1/org/create",
        json={
            "organization_name": "admin",  # Reserved name
            "email": TEST_ADMIN_EMAIL,
            "password": TEST_ADMIN_PASSWORD
        }
    )
    
    assert response.status_code == 422


# ============================================================================
# ORGANIZATION GET TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_get_organization_success(client, created_org):
    """Test successful organization retrieval."""
    response = await client.get(
        "/api/v1/org/get",
        params={"organization_name": TEST_ORG_NAME}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["organization_name"] == TEST_ORG_NAME
    assert data["admin_email"] == TEST_ADMIN_EMAIL


@pytest.mark.asyncio
async def test_get_organization_not_found(client):
    """Test getting non-existent organization returns 404."""
    response = await client.get(
        "/api/v1/org/get",
        params={"organization_name": "Nonexistent Org"}
    )
    
    assert response.status_code == 404
    data = response.json()
    assert "not found" in data["detail"]


# ============================================================================
# AUTHENTICATION TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_admin_login_success(client, created_org):
    """Test successful admin login."""
    response = await client.post(
        "/api/v1/admin/login",
        json={
            "email": TEST_ADMIN_EMAIL,
            "password": TEST_ADMIN_PASSWORD
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert "expires_in" in data


@pytest.mark.asyncio
async def test_admin_login_invalid_email(client, created_org):
    """Test login with invalid email returns 401."""
    response = await client.post(
        "/api/v1/admin/login",
        json={
            "email": "wrong@example.com",
            "password": TEST_ADMIN_PASSWORD
        }
    )
    
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_admin_login_invalid_password(client, created_org):
    """Test login with invalid password returns 401."""
    response = await client.post(
        "/api/v1/admin/login",
        json={
            "email": TEST_ADMIN_EMAIL,
            "password": "WrongPass123!"
        }
    )
    
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_verify_token_valid(client, admin_token):
    """Test token verification with valid token."""
    response = await client.post(
        "/api/v1/admin/verify",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is True
    assert data["admin_email"] == TEST_ADMIN_EMAIL


@pytest.mark.asyncio
async def test_verify_token_invalid(client):
    """Test token verification with invalid token."""
    response = await client.post(
        "/api/v1/admin/verify",
        headers={"Authorization": "Bearer invalid_token"}
    )
    
    assert response.status_code == 401


# ============================================================================
# ORGANIZATION UPDATE TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_update_organization_name(client, created_org, admin_token):
    """Test updating organization name."""
    response = await client.put(
        "/api/v1/org/update",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "organization_name": TEST_ORG_NAME,
            "new_organization_name": "Updated Test Organization"
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "updated successfully" in data["message"]


@pytest.mark.asyncio
async def test_update_organization_email(client, created_org, admin_token):
    """Test updating admin email."""
    response = await client.put(
        "/api/v1/org/update",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "organization_name": TEST_ORG_NAME,
            "email": "newemail@example.com"
        }
    )
    
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_update_organization_password(client, created_org, admin_token):
    """Test updating admin password."""
    response = await client.put(
        "/api/v1/org/update",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "organization_name": TEST_ORG_NAME,
            "password": "NewTestPass123!"
        }
    )
    
    assert response.status_code == 200
    
    # Verify new password works
    login_response = await client.post(
        "/api/v1/admin/login",
        json={
            "email": TEST_ADMIN_EMAIL,
            "password": "NewTestPass123!"
        }
    )
    assert login_response.status_code == 200


@pytest.mark.asyncio
async def test_update_organization_unauthorized(client, created_org):
    """Test updating organization without token returns 401."""
    response = await client.put(
        "/api/v1/org/update",
        json={
            "organization_name": TEST_ORG_NAME,
            "new_organization_name": "Updated Name"
        }
    )
    
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_update_organization_not_found(client, admin_token):
    """Test updating non-existent organization returns 404."""
    response = await client.put(
        "/api/v1/org/update",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "organization_name": "Nonexistent Org",
            "new_organization_name": "New Name"
        }
    )
    
    assert response.status_code == 404


# ============================================================================
# ORGANIZATION DELETE TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_delete_organization_success(client, created_org, admin_token):
    """Test successful organization deletion."""
    response = await client.delete(
        "/api/v1/org/delete",
        headers={"Authorization": f"Bearer {admin_token}"},
        params={"organization_name": TEST_ORG_NAME}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    
    # Verify organization is deleted
    get_response = await client.get(
        "/api/v1/org/get",
        params={"organization_name": TEST_ORG_NAME}
    )
    assert get_response.status_code == 404


@pytest.mark.asyncio
async def test_delete_organization_unauthorized(client, created_org):
    """Test deleting organization without token returns 401."""
    response = await client.delete(
        "/api/v1/org/delete",
        params={"organization_name": TEST_ORG_NAME}
    )
    
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_delete_organization_not_found(client, admin_token):
    """Test deleting non-existent organization returns 404."""
    response = await client.delete(
        "/api/v1/org/delete",
        headers={"Authorization": f"Bearer {admin_token}"},
        params={"organization_name": "Nonexistent Org"}
    )
    
    assert response.status_code == 404


# ============================================================================
# SERVICE LAYER TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_organization_exists(cleanup_test_orgs):
    """Test organization_exists service method."""
    # Should not exist initially
    exists = await organization_service.organization_exists(TEST_ORG_NAME)
    assert exists is False
    
    # Create organization
    await organization_service.create_organization(
        TEST_ORG_NAME,
        TEST_ADMIN_EMAIL,
        TEST_ADMIN_PASSWORD
    )
    
    # Should exist now
    exists = await organization_service.organization_exists(TEST_ORG_NAME)
    assert exists is True


@pytest.mark.asyncio
async def test_get_organization_stats(created_org):
    """Test organization statistics retrieval."""
    stats = await organization_service.get_organization_stats()
    
    assert "total_organizations" in stats
    assert "shared_database_orgs" in stats
    assert "dedicated_database_orgs" in stats
    assert stats["total_organizations"] >= 1


@pytest.mark.asyncio
async def test_password_hashing():
    """Test password is properly hashed and not stored in plain text."""
    from app.auth import hash_password, verify_password
    
    plain_password = "TestPassword123!"
    hashed = hash_password(plain_password)
    
    # Hash should be different from plain text
    assert hashed != plain_password
    
    # Should verify correctly
    assert verify_password(plain_password, hashed) is True
    
    # Should not verify with wrong password
    assert verify_password("WrongPassword123!", hashed) is False


# ============================================================================
# EDGE CASES & SECURITY TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_sql_injection_protection(client, cleanup_test_orgs):
    """Test SQL injection attempts are handled safely."""
    response = await client.post(
        "/api/v1/org/create",
        json={
            "organization_name": "Test'; DROP TABLE organizations; --",
            "email": TEST_ADMIN_EMAIL,
            "password": TEST_ADMIN_PASSWORD
        }
    )
    
    # Should either create safely or reject
    assert response.status_code in [201, 422]


@pytest.mark.asyncio
async def test_xss_protection(client, cleanup_test_orgs):
    """Test XSS attempts are handled safely."""
    response = await client.post(
        "/api/v1/org/create",
        json={
            "organization_name": "<script>alert('XSS')</script>",
            "email": TEST_ADMIN_EMAIL,
            "password": TEST_ADMIN_PASSWORD
        }
    )
    
    # Should be rejected by validation
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_concurrent_organization_creation(client, cleanup_test_orgs):
    """Test concurrent creation of same organization."""
    import asyncio
    
    async def create_org():
        return await client.post(
            "/api/v1/org/create",
            json={
                "organization_name": "Concurrent Test Org",
                "email": f"test{asyncio.current_task().get_name()}@example.com",
                "password": TEST_ADMIN_PASSWORD
            }
        )
    
    # Create 5 concurrent requests
    tasks = [create_org() for _ in range(5)]
    responses = await asyncio.gather(*tasks)
    
    # Only one should succeed (201), others should fail (409)
    success_count = sum(1 for r in responses if r.status_code == 201)
    assert success_count == 1
