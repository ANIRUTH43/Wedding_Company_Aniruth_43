# Wedding Company Aniruth 43

## 🎯 Project Overview

**Wedding_Company_Aniruth_43** is a multi-tenant FastAPI-based organization management system with MongoDB integration. It supports both **shared and dedicated database architectures**, enabling wedding companies and event management organizations to manage their operations efficiently with role-based admin controls and secure authentication.

### Key Features

- 🏢 **Multi-Tenant Architecture**: Support for multiple independent organizations
- 🔐 **JWT Authentication**: Secure token-based admin authentication with 7-day expiry
- 💾 **Flexible Database Models**:
  - **Shared Database Mode**: Cost-effective, multiple organizations in one database
  - **Dedicated Database Mode**: Isolated databases for enterprise clients
- ⚡ **Rate Limiting**: API rate limiting to prevent abuse (10 requests/min for org operations, 5/min for login)
- 📊 **Comprehensive Logging**: Structured logging for monitoring and debugging
- 🛡️ **Error Handling**: Standardized error responses with request tracking
- 🔍 **Health Checks**: Built-in health and metrics endpoints
- 📝 **API Documentation**: Interactive Swagger UI and ReDoc documentation

---

## 📁 Project Structure

```
Wedding_Company_Aniruth_43/
├── app/
│   ├── __init__.py              # Package initialization
│   ├── main.py                  # FastAPI application setup, middlewares, exception handlers
│   ├── routes.py                # API endpoints for organizations and authentication
│   ├── schemas.py               # Pydantic models for request/response validation
│   ├── services.py              # Business logic for organization management
│   ├── auth.py                  # JWT token creation and verification
│   ├── db.py                    # MongoDB connection management
│   ├── crud.py                  # CRUD operations for organizations
│   ├── logger.py                # Structured logging configuration
│   └── utils.py                 # Utility functions
├── tests/                       # Test suite
├── test_api.py                  # Comprehensive API test script
├── requirements.txt             # Python dependencies
├── .gitignore                   # Git ignore rules
└── README.md                    # This file
```

---

## 🚀 Installation & Setup

### Prerequisites

- **Python**: 3.8 or higher
- **MongoDB**: Local instance or MongoDB Atlas cloud connection
- **pip**: Python package manager

### Step 1: Clone the Repository

```bash
git clone https://github.com/ANIRUTH43/Wedding_Company_Aniruth_43.git
cd Wedding_Company_Aniruth_43
```

### Step 2: Create Virtual Environment

```bash
# On Windows
python -m venv venv
venv\Scripts\activate

# On macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 4: Configure Environment Variables

Create a `.env` file in the project root:

```bash
# MongoDB Connection
MONGODB_URI=give your own uri
MONGODB_DB_NAME=give your own name for it 

# Application Settings
ENVIRONMENT=development  # or production
LOG_LEVEL=INFO

# CORS Configuration
CORS_ENABLED=true
CORS_ORIGINS=http://localhost:3000,http://localhost:8000

# JWT Settings
JWT_SECRET_KEY=your-super-secret-key-change-in-production
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=10080  # 7 days
```

### Step 5: Run the Application

```bash
python -m app.main
```

The server will start at `http://localhost:8000`

---

## 📚 API Documentation

### Interactive Documentation

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI Schema**: http://localhost:8000/openapi.json

### Health Check Endpoints

```bash
# Root endpoint
GET /

# Health check with database status
GET /health

# Metrics endpoint
GET /metrics
```

---

## 🔧 Core API Endpoints

### Authentication Endpoints

#### Admin Login
```http
POST /api/v1/admin/login
Content-Type: application/json

{
  "email": "admin@acme.com",
  "password": "SecurePass123!"
}

Response (200):
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 604800
}
```

#### Verify Token
```http
POST /api/v1/admin/verify
Authorization: Bearer <token>

Response (200):
{
  "valid": true,
  "admin_email": "admin@acme.com",
  "org_id": "507f1f77bcf86cd799439011",
  "org_name": "Acme Corporation"
}
```

### Organization Endpoints

#### Create Organization
```http
POST /api/v1/org/create
Content-Type: application/json

{
  "organization_name": "Acme Corporation",
  "email": "admin@acme.com",
  "password": "SecurePass123!",
  "db_uri": "mongodb+srv://...",  # Optional - for dedicated mode
  "db_name": "acme_db"             # Optional - for dedicated mode
}

Response (201):
{
  "organization_name": "Acme Corporation",
  "collection_name": "acme_corporation",
  "admin_email": "admin@acme.com",
  "db_type": "shared",
  "created_at": "2024-12-12T10:00:00"
}
```

#### Get Organization
```http
GET /api/v1/org/get?organization_name=Acme%20Corporation

Response (200):
{
  "organization_name": "Acme Corporation",
  "collection_name": "acme_corporation",
  "admin_email": "admin@acme.com",
  "db_type": "shared",
  "created_at": "2024-12-12T10:00:00"
}
```

#### Update Organization
```http
PUT /api/v1/org/update
Authorization: Bearer <token>
Content-Type: application/json

{
  "organization_name": "Acme Corporation",
  "new_organization_name": "Acme Corp Ltd",
  "email": "newadmin@acme.com",
  "password": "NewSecurePass123!",
  "db_uri": null,
  "db_name": null
}

Response (200):
{
  "success": true,
  "message": "Organization updated successfully",
  "data": {"organization_name": "Acme Corp Ltd"}
}
```

#### Delete Organization
```http
DELETE /api/v1/org/delete?organization_name=Acme%20Corporation
Authorization: Bearer <token>

Response (200):
{
  "success": true,
  "message": "Organization 'Acme Corporation' deleted successfully",
  "data": {"organization_name": "Acme Corporation"}
}
```

---

## 🧪 Testing

### Run API Tests

```bash
python test_api.py
```

This will:
1. Test all CRUD operations
2. Verify authentication flows
3. Validate error handling
4. Save test results to `test_results.txt`

### Manual Testing with cURL

```bash
# Create organization
curl -X POST http://localhost:8000/api/v1/org/create \
  -H "Content-Type: application/json" \
  -d '{
    "organization_name": "Test Company",
    "email": "admin@testco.com",
    "password": "TestPass123!"
  }'

# Get organization
curl http://localhost:8000/api/v1/org/get?organization_name=Test%20Company

# Login
curl -X POST http://localhost:8000/api/v1/admin/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@testco.com",
    "password": "TestPass123!"
  }'

# Update organization (with token)
curl -X PUT http://localhost:8000/api/v1/org/update \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "organization_name": "Test Company",
    "new_organization_name": "Updated Company"
  }'
```

---

## 📋 Database Schema

### Organizations Collection

```json
{
  "_id": ObjectId,
  "organization_name": "string",
  "collection_name": "string",
  "admin": {
    "email": "string",
    "password": "hashed_string",
    "created_at": "datetime"
  },
  "db_type": "shared | dedicated",
  "db_uri": "string (optional)",
  "db_name": "string (optional)",
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

---

## 🔒 Security Features

### Password Validation
- Minimum 8 characters
- At least one uppercase letter
- At least one lowercase letter
- At least one digit
- Bcrypt hashing with salt rounds

### Authentication
- JWT tokens with HS256 algorithm
- 7-day token expiry
- Bearer token scheme
- Token payload includes:
  - Admin email (`sub`)
  - Organization ID (`org_id`)
  - Organization name (`org_name`)

### Rate Limiting
- Organization operations: 10 requests/minute
- Login endpoint: 5 requests/minute
- IP-based rate limiting

---

## 📊 Logging

The application uses structured logging with the following levels:

- **DEBUG**: Detailed information for debugging
- **INFO**: General informational messages
- **WARNING**: Warning messages for potential issues
- **ERROR**: Error messages for exceptions

### Sample Log Output

```
[2024-12-12 10:30:15] INFO: request_started request_id=abc123 method=POST path=/api/v1/org/create
[2024-12-12 10:30:16] INFO: org_created_successfully org_name=Acme Corporation org_id=507f1f77bcf86cd799439011
[2024-12-12 10:30:16] INFO: request_completed request_id=abc123 method=POST path=/api/v1/org/create status_code=201 duration_seconds=0.847
```

---

## 🐛 Troubleshooting

### MongoDB Connection Issues

```bash
# Verify MongoDB connection string
# Check if MongoDB service is running
# For local MongoDB: mongod should be running
# For MongoDB Atlas: Verify IP whitelist includes your IP
```

### Port Already in Use

```bash
# If port 8000 is already in use, modify in main.py:
uvicorn.run(
    "app.main:app",
    host="0.0.0.0",
    port=8001,  # Change port number
)
```

### Environment Variables Not Loading

```bash
# Ensure .env file is in the root directory
# Load dotenv is called at the start of main.py
# Restart the application after changing .env
```

---

## 📦 Dependencies

- **fastapi**: Web framework
- **uvicorn**: ASGI server
- **pymongo**: MongoDB driver
- **python-jose**: JWT handling
- **passlib**: Password hashing
- **python-multipart**: Form data handling
- **slowapi**: Rate limiting
- **python-dotenv**: Environment variable management
- **pydantic**: Data validation

See `requirements.txt` for complete list with versions.

---

## 🤝 Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📄 License

This project is open source and available under the MIT License.

---

## 👤 Author

**ANIRUTH43** - [GitHub Profile](https://github.com/ANIRUTH43)

For questions or support, feel free to reach out or open an issue.

---

## 🔗 Useful Links

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [MongoDB Documentation](https://docs.mongodb.com/)
- [JWT Introduction](https://jwt.io/introduction)
- [Pydantic Documentation](https://docs.pydantic.dev/)

---

**Last Updated**: December 2024
