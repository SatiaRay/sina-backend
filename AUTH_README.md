# Authentication System

This document describes the authentication system implemented for the AI Chatbot application.

## Features

- **User Registration**: Create new user accounts with email and password
- **User Login**: Authenticate users and receive JWT tokens
- **User Types**: Support for Admin, Supporter, and Customer roles
- **Password Security**: Bcrypt hashing for secure password storage
- **JWT Tokens**: Secure token-based authentication
- **User Management**: Get current user info and logout functionality

## User Model

The `User` model includes the following fields:

- `id`: Primary key
- `email`: Unique email address (used for login)
- `password_hash`: Hashed password using bcrypt
- `first_name`: User's first name (optional)
- `last_name`: User's last name (optional)
- `user_type`: User role (admin, supporter, customer)
- `is_active`: Account status (can be disabled)
- `is_verified`: Email verification status
- `last_login`: Timestamp of last login
- `email_verified_at`: Email verification timestamp
- `created_at`: Account creation timestamp
- `updated_at`: Last update timestamp

## API Endpoints

### Authentication Endpoints

#### POST `/auth/register`
Register a new user account.

**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "securepassword123",
  "first_name": "John",
  "last_name": "Doe",
  "user_type": "customer"
}
```

**Response (201):**
```json
{
  "id": 1,
  "email": "user@example.com",
  "first_name": "John",
  "last_name": "Doe",
  "user_type": "customer",
  "is_active": true,
  "is_verified": false,
  "created_at": "2024-01-01T00:00:00"
}
```

#### POST `/auth/login`
Login user and receive access token.

**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "securepassword123"
}
```

**Response (200):**
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "token_type": "bearer",
  "user": {
    "id": 1,
    "email": "user@example.com",
    "first_name": "John",
    "last_name": "Doe",
    "user_type": "customer",
    "is_active": true,
    "is_verified": false,
    "created_at": "2024-01-01T00:00:00"
  }
}
```

#### GET `/auth/me`
Get current user information (requires authentication).

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response (200):**
```json
{
  "id": 1,
  "email": "user@example.com",
  "first_name": "John",
  "last_name": "Doe",
  "user_type": "customer",
  "is_active": true,
  "is_verified": false,
  "created_at": "2024-01-01T00:00:00"
}
```

#### POST `/auth/logout`
Logout user (client-side token discard).

**Response (200):**
```json
{
  "message": "Successfully logged out"
}
```

## User Types

### Customer
- Default user type
- Basic access to chat functionality
- Can view and interact with the chatbot

### Supporter
- Support staff access
- Can help customers and manage support tickets
- Extended access to system features

### Admin
- Full system access
- Can manage users, content, and system settings
- Highest level of permissions

## Security Features

### Password Security
- Passwords are hashed using bcrypt
- Salt is automatically generated
- Secure against rainbow table attacks

### JWT Tokens
- Tokens expire after 30 minutes by default
- Uses HS256 algorithm for signing
- Tokens contain user email as subject

### Input Validation
- Email format validation
- Password strength requirements (can be enhanced)
- User type validation

## Environment Variables

Add these to your `.env` file:

```env
# JWT Configuration
JWT_SECRET_KEY=your-super-secret-key-change-in-production

# Database Configuration (already configured)
MYSQL_HOST=127.0.0.1
MYSQL_USER=root
MYSQL_PASSWORD=
MYSQL_DATABASE=ai_db
MYSQL_PORT=3306
```

## Installation

1. Install the required dependencies:
```bash
pip install -r requirements.txt
```

2. Run the database migration:
```bash
alembic upgrade head
```

3. Start the application:
```bash
python -m uvicorn api.main:app --reload
```

## Testing

Run the authentication tests:

```bash
# Run all auth tests
python run_auth_tests.py

# Or run with pytest directly
pytest tests/api/test_auth.py -v
```

## Usage Examples

### Register a new user
```bash
curl -X POST "http://localhost:8000/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "securepassword123",
    "first_name": "John",
    "last_name": "Doe",
    "user_type": "customer"
  }'
```

### Login user
```bash
curl -X POST "http://localhost:8000/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "securepassword123"
  }'
```

### Get current user info
```bash
curl -X GET "http://localhost:8000/auth/me" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

## Integration with Existing Endpoints

To protect existing endpoints with authentication, you can use the `get_current_user` dependency:

```python
from api.auth import get_current_user
from database.models import User

@app.get("/protected-endpoint")
async def protected_endpoint(current_user: User = Depends(get_current_user)):
    return {"message": f"Hello {current_user.email}!"}
```

## Future Enhancements

- [ ] Email verification system
- [ ] Password reset functionality
- [ ] Refresh tokens for longer sessions
- [ ] Role-based access control (RBAC)
- [ ] Two-factor authentication (2FA)
- [ ] Account lockout after failed attempts
- [ ] Password strength validation
- [ ] User profile management
- [ ] Admin user management interface 