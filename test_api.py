# test_api.py
"""
Comprehensive API test script that saves results to a text file.
Run this to test all endpoints and save output to test_results.txt
"""

import requests
import json
from datetime import datetime
import sys
import time

# Configuration
API_URL = "http://localhost:8000"
TEST_ORG_NAME = "Aniruth Wedding Company"
TEST_EMAIL = "admin@aniruthwedding.com"
TEST_PASSWORD = "SecurePass123!"
OUTPUT_FILE = "test_results.txt"

# Test counters
passed = 0
failed = 0
test_results = []


class TestLogger:
    """Logger that writes to both console and file"""
    
    def __init__(self, filename):
        self.filename = filename
        self.log_content = []
        
    def log(self, message, color=None):
        """Log message to console and memory"""
        print(message)
        self.log_content.append(message)
    
    def success(self, message):
        """Log success message"""
        global passed
        msg = f"✓ {message}"
        print(f"\033[92m{msg}\033[0m")  # Green
        self.log_content.append(msg)
        passed += 1
    
    def error(self, message):
        """Log error message"""
        global failed
        msg = f"✗ {message}"
        print(f"\033[91m{msg}\033[0m")  # Red
        self.log_content.append(msg)
        failed += 1
    
    def info(self, message):
        """Log info message"""
        msg = f"▶ {message}"
        print(f"\033[93m{msg}\033[0m")  # Yellow
        self.log_content.append(msg)
    
    def header(self, message):
        """Log header message"""
        separator = "=" * 60
        print(f"\033[94m\n{separator}\033[0m")  # Blue
        print(f"\033[94m{message}\033[0m")
        print(f"\033[94m{separator}\n\033[0m")
        self.log_content.append(f"\n{separator}")
        self.log_content.append(message)
        self.log_content.append(f"{separator}\n")
    
    def data(self, data_dict):
        """Log formatted JSON data"""
        formatted = json.dumps(data_dict, indent=2)
        print(formatted)
        self.log_content.append(formatted)
    
    def save(self):
        """Save all logs to file"""
        with open(self.filename, 'w', encoding='utf-8') as f:
            f.write(f"API Test Results\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 60 + "\n\n")
            f.write('\n'.join(self.log_content))
            f.write(f"\n\n{'=' * 60}\n")
            f.write(f"Test Summary\n")
            f.write(f"{'=' * 60}\n")
            f.write(f"Total Tests: {passed + failed}\n")
            f.write(f"Passed: {passed}\n")
            f.write(f"Failed: {failed}\n")
            f.write(f"Success Rate: {(passed/(passed+failed)*100):.2f}%\n" if (passed+failed) > 0 else "No tests run\n")


# Initialize logger
logger = TestLogger(OUTPUT_FILE)


def wait_for_api(max_attempts=30):
    """Wait for API to be ready"""
    logger.info("Waiting for API to be ready...")
    
    for i in range(max_attempts):
        try:
            response = requests.get(f"{API_URL}/health", timeout=2)
            if response.status_code == 200:
                logger.success("API is ready!")
                return True
        except:
            print(".", end="", flush=True)
            time.sleep(2)
    
    logger.error("API failed to start within timeout")
    return False


def test_root_endpoint():
    """Test 1: Root endpoint"""
    logger.info("Test 1: Root endpoint")
    
    try:
        response = requests.get(API_URL, timeout=5)
        data = response.json()
        
        if response.status_code == 200 and "Organization Management API" in data.get("service", ""):
            logger.success("Root endpoint working")
            logger.data(data)
            return True
        else:
            logger.error(f"Root endpoint failed - Status: {response.status_code}")
            logger.data(data)
            return False
    except Exception as e:
        logger.error(f"Root endpoint error: {str(e)}")
        return False


def test_health_check():
    """Test 2: Health check"""
    logger.info("Test 2: Health check")
    
    try:
        response = requests.get(f"{API_URL}/health", timeout=5)
        data = response.json()
        
        if response.status_code == 200 and data.get("status") == "healthy":
            logger.success("Health check passed")
            logger.data(data)
            return True
        else:
            logger.error(f"Health check failed - Status: {response.status_code}")
            logger.data(data)
            return False
    except Exception as e:
        logger.error(f"Health check error: {str(e)}")
        return False


def test_api_docs():
    """Test 3: API Documentation"""
    logger.info("Test 3: API Documentation")
    
    try:
        response = requests.get(f"{API_URL}/docs", timeout=5)
        
        if response.status_code == 200:
            logger.success("API docs accessible")
            logger.log(f"URL: {API_URL}/docs")
            return True
        else:
            logger.error(f"API docs failed - Status: {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"API docs error: {str(e)}")
        return False


def test_create_organization():
    """Test 4: Create organization"""
    logger.info("Test 4: Create organization")
    
    try:
        payload = {
            "organization_name": TEST_ORG_NAME,
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        }
        
        response = requests.post(
            f"{API_URL}/api/v1/org/create",
            json=payload,
            timeout=10
        )
        data = response.json()
        
        if response.status_code == 201 and data.get("organization_name") == TEST_ORG_NAME:
            logger.success("Organization created successfully")
            logger.data(data)
            return True
        elif response.status_code == 409:
            logger.success("Organization already exists (expected if running multiple times)")
            logger.data(data)
            return True
        else:
            logger.error(f"Create organization failed - Status: {response.status_code}")
            logger.data(data)
            return False
    except Exception as e:
        logger.error(f"Create organization error: {str(e)}")
        return False


def test_admin_login():
    """Test 5: Admin login"""
    logger.info("Test 5: Admin login")
    
    try:
        payload = {
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        }
        
        response = requests.post(
            f"{API_URL}/api/v1/admin/login",
            json=payload,
            timeout=10
        )
        data = response.json()
        
        if response.status_code == 200 and "access_token" in data:
            logger.success("Login successful")
            token = data["access_token"]
            logger.log(f"Token: {token[:50]}...")
            logger.data({"token_type": data.get("token_type"), "expires_in": data.get("expires_in")})
            return token
        else:
            logger.error(f"Login failed - Status: {response.status_code}")
            logger.data(data)
            return None
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        return None


def test_get_organization():
    """Test 6: Get organization"""
    logger.info("Test 6: Get organization details")
    
    try:
        response = requests.get(
            f"{API_URL}/api/v1/org/get",
            params={"organization_name": TEST_ORG_NAME},
            timeout=5
        )
        data = response.json()
        
        if response.status_code == 200 and data.get("organization_name") == TEST_ORG_NAME:
            logger.success("Organization retrieved successfully")
            logger.data(data)
            return True
        else:
            logger.error(f"Get organization failed - Status: {response.status_code}")
            logger.data(data)
            return False
    except Exception as e:
        logger.error(f"Get organization error: {str(e)}")
        return False


def test_verify_token(token):
    """Test 7: Verify token"""
    logger.info("Test 7: Verify token")
    
    if not token:
        logger.error("No token available for verification")
        return False
    
    try:
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.post(
            f"{API_URL}/api/v1/admin/verify",
            headers=headers,
            timeout=5
        )
        data = response.json()
        
        if response.status_code == 200 and data.get("valid"):
            logger.success("Token verified successfully")
            logger.data(data)
            return True
        else:
            logger.error(f"Token verification failed - Status: {response.status_code}")
            logger.data(data)
            return False
    except Exception as e:
        logger.error(f"Token verification error: {str(e)}")
        return False


def test_update_organization(token):
    """Test 8: Update organization"""
    logger.info("Test 8: Update organization")
    
    if not token:
        logger.error("No token available for update")
        return False
    
    try:
        headers = {"Authorization": f"Bearer {token}"}
        payload = {
            "organization_name": TEST_ORG_NAME,
            "new_organization_name": "Aniruth Premium Weddings"
        }
        
        response = requests.put(
            f"{API_URL}/api/v1/org/update",
            json=payload,
            headers=headers,
            timeout=10
        )
        data = response.json()
        
        if response.status_code == 200 and data.get("success"):
            logger.success("Organization updated successfully")
            logger.data(data)
            return True
        else:
            logger.error(f"Update organization failed - Status: {response.status_code}")
            logger.data(data)
            return False
    except Exception as e:
        logger.error(f"Update organization error: {str(e)}")
        return False


def test_metrics():
    """Test 9: Metrics endpoint"""
    logger.info("Test 9: Metrics endpoint")
    
    try:
        response = requests.get(f"{API_URL}/metrics", timeout=5)
        data = response.json()
        
        if response.status_code == 200 and "organizations_total" in data:
            logger.success("Metrics endpoint working")
            logger.data(data)
            return True
        else:
            logger.error(f"Metrics failed - Status: {response.status_code}")
            logger.data(data)
            return False
    except Exception as e:
        logger.error(f"Metrics error: {str(e)}")
        return False


def test_delete_organization(token):
    """Test 10: Delete organization (optional - commented out by default)"""
    logger.info("Test 10: Delete organization (SKIPPED - preserving data)")
    logger.log("To enable deletion, uncomment the code in test_api.py")
    
    # Uncomment below to actually delete
    """
    if not token:
        logger.error("No token available for deletion")
        return False
    
    try:
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.delete(
            f"{API_URL}/api/v1/org/delete",
            params={"organization_name": "Aniruth Premium Weddings"},
            headers=headers,
            timeout=10
        )
        data = response.json()
        
        if response.status_code == 200 and data.get("success"):
            logger.success("Organization deleted successfully")
            logger.data(data)
            return True
        else:
            logger.error(f"Delete organization failed - Status: {response.status_code}")
            logger.data(data)
            return False
    except Exception as e:
        logger.error(f"Delete organization error: {str(e)}")
        return False
    """
    return True


def run_all_tests():
    """Run all tests in sequence"""
    logger.header("🧪 COMPREHENSIVE API TEST SUITE")
    logger.log(f"API URL: {API_URL}")
    logger.log(f"Test Organization: {TEST_ORG_NAME}")
    logger.log(f"Test Email: {TEST_EMAIL}")
    logger.log(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Check if API is running
    logger.header("📋 PREREQUISITES CHECK")
    if not wait_for_api():
        logger.error("API is not running. Please start the API first:")
        logger.log("  uvicorn app.main:app --reload --host 0.0.0.0 --port 8000")
        logger.save()
        sys.exit(1)
    
    # Run tests
    logger.header("🌐 API ENDPOINT TESTS")
    
    test_root_endpoint()
    test_health_check()
    test_api_docs()
    test_create_organization()
    
    # Login and get token
    token = test_admin_login()
    
    test_get_organization()
    test_verify_token(token)
    test_update_organization(token)
    test_metrics()
    test_delete_organization(token)
    
    # Summary
    logger.header("📊 TEST SUMMARY")
    total = passed + failed
    success_rate = (passed / total * 100) if total > 0 else 0
    
    logger.log(f"Total Tests: {total}")
    logger.log(f"Passed: {passed} ✓")
    logger.log(f"Failed: {failed} ✗")
    logger.log(f"Success Rate: {success_rate:.2f}%")
    
    if failed == 0:
        logger.log("\n🎉 ALL TESTS PASSED! 🎉")
    else:
        logger.log(f"\n⚠ {failed} TEST(S) FAILED")
    
    # Useful information
    logger.header("📌 USEFUL INFORMATION")
    logger.log(f"API Root:       {API_URL}")
    logger.log(f"API Docs:       {API_URL}/docs")
    logger.log(f"Health Check:   {API_URL}/health")
    logger.log(f"ReDoc:          {API_URL}/redoc")
    
    # Save results
    logger.save()
    print(f"\n✅ Test results saved to: {OUTPUT_FILE}")
    
    return failed == 0


if __name__ == "__main__":
    try:
        success = run_all_tests()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        logger.log("\n\nTest interrupted by user")
        logger.save()
        sys.exit(1)
    except Exception as e:
        print(f"\n\nUnexpected error: {str(e)}")
        logger.error(f"Unexpected error: {str(e)}")
        logger.save()
        sys.exit(1)
