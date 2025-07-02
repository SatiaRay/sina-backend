# User Management API

This document describes the comprehensive user management system implemented for the AI Chatbot application.

## Features

- **User Status Management**: Activate/deactivate user accounts
- **User Information Updates**: Edit user details, change user types
- **Password Management**: Secure password updates
- **User Deletion**: Safe user account removal
- **Advanced User Listing**: Pagination, search, filtering, and sorting
- **User Search**: Find users by email
- **Profile Management**: Users can manage their own profiles
- **Role-Based Access Control**: Admin-only operations with proper authorization

## API Endpoints

### Authentication Required
All endpoints require authentication via JWT Bearer token in the Authorization header:
```
Authorization: Bearer <your_jwt_token>
```

### Admin-Only Endpoints
Most user management operations require admin privileges. Regular users can only:
- View their own profile
- Update their own profile (limited fields)
- Change their own password

---

## 1. User Status Management

### PUT `/users/{user_id}/status`
Activate or deactivate a user account.

**Admin Only**

**Request Body:**
```json
{
  "is_active": true
}
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
  "last_login": "2024-01-01T10:00:00",
  "email_verified_at": null,
  "created_at": "2024-01-01T00:00:00",
  "updated_at": "2024-01-01T10:00:00",
  "chat_count": 5
}
```

**Security Rules:**
- Admins cannot deactivate their own account
- Admins cannot deactivate other admin accounts
- Only admins can perform this operation

---

## 2. User Information Updates

### PUT `/users/{user_id}`
Update user information (admin only).

**Admin Only**

**Request Body:**
```json
{
  "email": "updated@example.com",
  "first_name": "Updated",
  "last_name": "Name",
  "user_type": "supporter",
  "is_verified": true
}
```

**Response (200):**
```json
{
  "id": 1,
  "email": "updated@example.com",
  "first_name": "Updated",
  "last_name": "Name",
  "user_type": "supporter",
  "is_active": true,
  "is_verified": true,
  "last_login": "2024-01-01T10:00:00",
  "email_verified_at": "2024-01-01T10:00:00",
  "created_at": "2024-01-01T00:00:00",
  "updated_at": "2024-01-01T10:00:00",
  "chat_count": 5
}
```

**Security Rules:**
- Cannot change admin user types
- Email must be unique
- User type must be valid (admin, supporter, customer)

---

## 3. Password Management

### PUT `/users/{user_id}/password`
Update user password.

**Users can update their own password, admins can update any password**

**Request Body:**
```json
{
  "current_password": "oldpassword123",
  "new_password": "newpassword123"
}
```

**Response (200):**
```json
{
  "message": "Password updated successfully"
}
```

**Security Rules:**
- Users can only update their own password
- Admins can update any user's password
- Current password must be verified

---

## 4. User Deletion

### DELETE `/users/{user_id}`
Delete a user account.

**Admin Only**

**Response (200):**
```json
{
  "message": "User deleted successfully"
}
```

**Security Rules:**
- Admins cannot delete their own account
- Admin accounts cannot be deleted
- Only admins can perform this operation

---

## 5. User Listing with Advanced Features

### GET `/users/`
Get all users with pagination, search, filtering, and sorting.

**Admin Only**

**Query Parameters:**
- `page` (int, default: 1): Page number
- `per_page` (int, default: 10, max: 100): Items per page
- `search` (string, optional): Search in email, first name, or last name
- `user_type` (string, optional): Filter by user type (admin, supporter, customer)
- `is_active` (boolean, optional): Filter by active status
- `is_verified` (boolean, optional): Filter by verification status
- `sort_by` (string, default: "created_at"): Sort field
- `sort_order` (string, default: "desc"): Sort order (asc/desc)

**Example Request:**
```
GET /users/?page=1&per_page=20&search=john&user_type=customer&sort_by=email&sort_order=asc
```

**Response (200):**
```json
{
  "users": [
    {
      "id": 1,
      "email": "john@example.com",
      "first_name": "John",
      "last_name": "Doe",
      "user_type": "customer",
      "is_active": true,
      "is_verified": false,
      "last_login": "2024-01-01T10:00:00",
      "email_verified_at": null,
      "created_at": "2024-01-01T00:00:00",
      "updated_at": "2024-01-01T10:00:00"
    }
  ],
  "total": 1,
  "page": 1,
  "per_page": 20,
  "total_pages": 1,
  "has_next": false,
  "has_prev": false
}
```

**Available Sort Fields:**
- `id`
- `email`
- `first_name`
- `last_name`
- `user_type`
- `created_at`
- `updated_at`

---

## 6. User Detail Retrieval

### GET `/users/{user_id}`
Get detailed user information.

**Users can view their own details, admins can view any user**

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
  "last_login": "2024-01-01T10:00:00",
  "email_verified_at": null,
  "created_at": "2024-01-01T00:00:00",
  "updated_at": "2024-01-01T10:00:00",
  "chat_count": 5
}
```

**Security Rules:**
- Users can only view their own details
- Admins can view any user's details

---

## 7. User Search by Email

### GET `/users/search/{email}`
Find user by email address.

**Admin Only**

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
  "last_login": "2024-01-01T10:00:00",
  "email_verified_at": null,
  "created_at": "2024-01-01T00:00:00",
  "updated_at": "2024-01-01T10:00:00",
  "chat_count": 5
}
```

**Response (404):**
```json
{
  "detail": "User not found"
}
```

---

## 8. Profile Management

### GET `/users/me/profile`
Get current user's profile information.

**All authenticated users**

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
  "last_login": "2024-01-01T10:00:00",
  "email_verified_at": null,
  "created_at": "2024-01-01T00:00:00",
  "updated_at": "2024-01-01T10:00:00",
  "chat_count": 5
}
```

### PUT `/users/me/profile`
Update current user's profile.

**All authenticated users**

**Request Body:**
```json
{
  "email": "newemail@example.com",
  "first_name": "Updated",
  "last_name": "Name"
}
```

**Response (200):**
```json
{
  "message": "Profile updated successfully"
}
```

**Security Rules:**
- Users cannot change their own user_type
- Users cannot change their own verification status
- Email must be unique

---

## Usage Examples

### 1. Create an Admin User
```bash
# First register a user
curl -X POST "http://localhost:8000/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@example.com",
    "password": "adminpass123",
    "first_name": "Admin",
    "last_name": "User",
    "user_type": "admin"
  }'

# Login to get token
curl -X POST "http://localhost:8000/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@example.com",
    "password": "adminpass123"
  }'
```

### 2. List All Users with Pagination
```bash
curl -X GET "http://localhost:8000/users/?page=1&per_page=10" \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN"
```

### 3. Search Users
```bash
curl -X GET "http://localhost:8000/users/?search=john&user_type=customer" \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN"
```

### 4. Update User Status
```bash
curl -X PUT "http://localhost:8000/users/2/status" \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"is_active": false}'
```

### 5. Update User Information
```bash
curl -X PUT "http://localhost:8000/users/2" \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "first_name": "Updated",
    "last_name": "Name",
    "user_type": "supporter",
    "is_verified": true
  }'
```

### 6. Find User by Email
```bash
curl -X GET "http://localhost:8000/users/search/user@example.com" \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN"
```

### 7. Update Own Profile
```bash
curl -X PUT "http://localhost:8000/users/me/profile" \
  -H "Authorization: Bearer YOUR_USER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "first_name": "Updated",
    "last_name": "Name"
  }'
```

### 8. Change Password
```bash
curl -X PUT "http://localhost:8000/users/me/password" \
  -H "Authorization: Bearer YOUR_USER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "current_password": "oldpassword123",
    "new_password": "newpassword123"
  }'
```

---

## Error Responses

### 400 Bad Request
```json
{
  "detail": "Email already registered"
}
```

### 401 Unauthorized
```json
{
  "detail": "Could not validate credentials"
}
```

### 403 Forbidden
```json
{
  "detail": "Admin access required for this operation"
}
```

### 404 Not Found
```json
{
  "detail": "User not found"
}
```

### 500 Internal Server Error
```json
{
  "detail": "Failed to update user"
}
```

---

## Testing

Run the user management tests:

```bash
# Run all user management tests
python run_user_tests.py

# Or run with pytest directly
pytest tests/api/test_user.py -v
```

---

## Security Features

### Role-Based Access Control
- **Admin**: Full access to all user management operations
- **Supporter**: Limited access (can view own profile, update own password)
- **Customer**: Limited access (can view own profile, update own password)

### Data Protection
- Passwords are hashed using bcrypt
- Email addresses are validated
- User types are restricted to valid values
- Admin accounts have special protection

### Authorization Rules
- Users can only access their own data
- Admins cannot modify other admin accounts
- Admins cannot delete their own account
- Email uniqueness is enforced

---

## Integration with Existing System

The user management system integrates seamlessly with the existing authentication system:

1. **Shared Models**: Uses the same User model from `database/models.py`
2. **Shared Authentication**: Uses the same JWT authentication from `api/auth.py`
3. **Database Integration**: Works with existing database migrations
4. **API Consistency**: Follows the same patterns as other API endpoints

---

## Future Enhancements

- [ ] Bulk user operations (import/export)
- [ ] User activity logging
- [ ] Advanced user analytics
- [ ] User groups and permissions
- [ ] Email notifications for user changes
- [ ] User session management
- [ ] Two-factor authentication integration
- [ ] User audit trail 