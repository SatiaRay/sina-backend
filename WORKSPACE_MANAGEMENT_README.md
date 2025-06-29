# Workspace Management API

This document describes the comprehensive workspace management system implemented for the AI Chatbot application.

## Features

- **Workspace Creation**: Create workspaces with owners (customer users only)
- **Workspace Management**: Update, delete, and list workspaces
- **User Management**: Add/remove users to/from workspaces with different roles
- **Role-Based Access**: Owner, admin, member, and viewer roles
- **Workspace Listing**: Get all workspaces with pagination
- **User Listing**: List all users in a specific workspace
- **Security**: Proper validation and access control

## API Endpoints

### Authentication Required
All endpoints require authentication via JWT Bearer token in the Authorization header:
```
Authorization: Bearer <your_jwt_token>
```

### Access Control
- Workspace owners have full control over their workspaces
- Only customer users can be workspace owners
- Users can be added to multiple workspaces with different roles

---

## 1. Workspace Creation

### POST `/workspaces/`
Create a new workspace.

**Request Body:**
```json
{
  "name": "My Workspace",
  "description": "A workspace for my team",
  "owner_id": 1
}
```

**Response (200):**
```json
{
  "id": 1,
  "name": "My Workspace",
  "description": "A workspace for my team",
  "owner_id": 1,
  "is_active": true,
  "created_at": "2024-01-01T00:00:00",
  "updated_at": "2024-01-01T00:00:00"
}
```

**Security Rules:**
- Owner must be a valid customer user
- Owner is automatically added to workspace with 'owner' role
- Workspace name is required

---

## 2. Workspace Listing

### GET `/workspaces/`
Get all workspaces with pagination.

**Query Parameters:**
- `page` (int, default: 1): Page number (starting from 1)
- `per_page` (int, default: 10): Number of workspaces per page (max: 100)

**Example Request:**
```
GET /workspaces/?page=1&per_page=5
```

**Response (200):**
```json
{
  "workspaces": [
    {
      "id": 1,
      "name": "My Workspace",
      "description": "A workspace for my team",
      "owner_id": 1,
      "is_active": true
    },
    {
      "id": 2,
      "name": "Another Workspace",
      "description": "Another team workspace",
      "owner_id": 2,
      "is_active": true
    }
  ],
  "total": 2,
  "page": 1,
  "per_page": 5,
  "total_pages": 1,
  "has_next": false,
  "has_prev": false
}
```

---

## 3. Workspace Detail Retrieval

### GET `/workspaces/{workspace_id}`
Get detailed workspace information.

**Response (200):**
```json
{
  "id": 1,
  "name": "My Workspace",
  "description": "A workspace for my team",
  "owner_id": 1,
  "is_active": true,
  "created_at": "2024-01-01T00:00:00",
  "updated_at": "2024-01-01T00:00:00"
}
```

**Response (404):**
```json
{
  "detail": "Workspace not found"
}
```

---

## 4. Workspace Updates

### PUT `/workspaces/{workspace_id}`
Update workspace information.

**Request Body:**
```json
{
  "name": "Updated Workspace Name",
  "description": "Updated description",
  "is_active": false
}
```

**Response (200):**
```json
{
  "id": 1,
  "name": "Updated Workspace Name",
  "description": "Updated description",
  "owner_id": 1,
  "is_active": false,
  "created_at": "2024-01-01T00:00:00",
  "updated_at": "2024-01-01T10:00:00"
}
```

**Security Rules:**
- All fields are optional
- Only provided fields will be updated

---

## 5. Workspace Deletion

### DELETE `/workspaces/{workspace_id}`
Delete a workspace.

**Response (204):**
No content returned.

**Security Rules:**
- Workspace and all associated user relationships are deleted
- This action cannot be undone

---

## 6. User Management in Workspaces

### POST `/workspaces/{workspace_id}/users`
Add a user to a workspace.

**Request Body:**
```json
{
  "user_id": 2,
  "role": "member"
}
```

**Response (200):**
```json
{
  "user_id": 2,
  "role": "member",
  "joined_at": "2024-01-01T10:00:00"
}
```

**Available Roles:**
- `owner`: Full control over workspace
- `admin`: Administrative privileges
- `member`: Standard member access
- `viewer`: Read-only access

**Security Rules:**
- User must exist in the system
- User cannot be added if already in workspace
- Default role is 'member' if not specified

---

## 7. Remove User from Workspace

### DELETE `/workspaces/{workspace_id}/users/{user_id}`
Remove a user from a workspace.

**Response (204):**
No content returned.

**Security Rules:**
- User must be currently in the workspace
- Owner cannot be removed from their own workspace

---

## 8. List Workspace Users

### GET `/workspaces/{workspace_id}/users`
Get all users in a specific workspace.

**Response (200):**
```json
[
  {
    "user_id": 1,
    "role": "owner",
    "joined_at": "2024-01-01T00:00:00"
  },
  {
    "user_id": 2,
    "role": "member",
    "joined_at": "2024-01-01T10:00:00"
  },
  {
    "user_id": 3,
    "role": "viewer",
    "joined_at": "2024-01-01T11:00:00"
  }
]
```

---

## Usage Examples

### 1. Create a Workspace
```bash
curl -X POST "http://localhost:8000/workspaces/" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Development Team",
    "description": "Workspace for the development team",
    "owner_id": 1
  }'
```

### 2. List All Workspaces
```bash
curl -X GET "http://localhost:8000/workspaces/?page=1&per_page=5" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### 3. Get Workspace Details
```bash
curl -X GET "http://localhost:8000/workspaces/1" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### 4. Update Workspace
```bash
curl -X PUT "http://localhost:8000/workspaces/1" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Updated Development Team",
    "description": "Updated description"
  }'
```

### 5. Add User to Workspace
```bash
curl -X POST "http://localhost:8000/workspaces/1/users" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": 2,
    "role": "admin"
  }'
```

### 6. List Workspace Users
```bash
curl -X GET "http://localhost:8000/workspaces/1/users" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### 7. Remove User from Workspace
```bash
curl -X DELETE "http://localhost:8000/workspaces/1/users/2" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### 8. Delete Workspace
```bash
curl -X DELETE "http://localhost:8000/workspaces/1" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

---

## Error Responses

### 400 Bad Request
```json
{
  "detail": "Owner must be a valid customer user."
}
```

```json
{
  "detail": "User already in workspace"
}
```

### 404 Not Found
```json
{
  "detail": "Workspace not found"
}
```

```json
{
  "detail": "User not found"
}
```

```json
{
  "detail": "User not in workspace"
}
```

### 500 Internal Server Error
```json
{
  "detail": "Internal server error"
}
```

---

## Testing

Run the workspace management tests:

```bash
# Run all workspace tests
pytest tests/api/test_workspace.py -v

# Run specific test
pytest tests/api/test_workspace.py::test_create_workspace -v
```

---

## Database Schema

### Workspace Model
```sql
CREATE TABLE workspaces (
    id INTEGER PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    owner_id INTEGER NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (owner_id) REFERENCES users(id)
);
```

### WorkspaceUser Model (Association Table)
```sql
CREATE TABLE workspace_users (
    id INTEGER PRIMARY KEY AUTO_INCREMENT,
    workspace_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    role ENUM('owner', 'admin', 'member', 'viewer') DEFAULT 'member',
    joined_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (workspace_id) REFERENCES workspaces(id),
    FOREIGN KEY (user_id) REFERENCES users(id)
);
```

---

## Security Features

### Role-Based Access Control
- **Owner**: Full control over workspace (create, update, delete, manage users)
- **Admin**: Administrative privileges (manage users, update workspace)
- **Member**: Standard access (view workspace, participate in activities)
- **Viewer**: Read-only access (view workspace and users)

### Data Protection
- Workspace owners must be customer users
- Users cannot be added to the same workspace multiple times
- Proper foreign key constraints ensure data integrity
- Soft deletion support through `is_active` flag

### Validation Rules
- Workspace name is required
- Owner must be a valid customer user
- User must exist before being added to workspace
- Role must be one of: owner, admin, member, viewer

---

## Integration with Existing System

The workspace management system integrates seamlessly with the existing user management system:

1. **Shared Models**: Uses the same User model from `database/models.py`
2. **Shared Authentication**: Uses the same JWT authentication from `api/auth.py`
3. **Database Integration**: Works with existing database migrations
4. **API Consistency**: Follows the same patterns as other API endpoints

---

## Business Logic

### Workspace Ownership
- Only customer users can be workspace owners
- When a workspace is created, the owner is automatically added with 'owner' role
- Owners have full control over their workspaces

### User Management
- Users can belong to multiple workspaces with different roles
- Each user-workspace relationship is tracked separately
- Users can be promoted or demoted by changing their role

### Workspace Lifecycle
1. **Creation**: Workspace is created with an owner
2. **Management**: Users are added/removed, roles are assigned
3. **Deletion**: Workspace and all user relationships are removed

---

## Future Enhancements

- [ ] Workspace templates and cloning
- [ ] Advanced role permissions (granular permissions)
- [ ] Workspace activity logging
- [ ] Workspace analytics and reporting
- [ ] Bulk user operations (import/export users)
- [ ] Workspace invitations and approval workflows
- [ ] Workspace backup and restore
- [ ] Workspace sharing and collaboration features
- [ ] Workspace-specific settings and configurations
- [ ] Workspace audit trail
- [ ] Workspace notifications and alerts
- [ ] Workspace resource management (storage, API limits)
- [ ] Workspace branding and customization
- [ ] Workspace integration with external tools
- [ ] Workspace performance monitoring

---

## API Versioning

The workspace API follows the same versioning strategy as the rest of the application. All endpoints are prefixed with `/workspaces/` and are part of the main API version.

---

## Rate Limiting

Workspace API endpoints are subject to the same rate limiting policies as other API endpoints in the application.

---

## Monitoring and Logging

All workspace operations are logged for audit purposes:
- Workspace creation, updates, and deletion
- User additions and removals
- Role changes
- Access attempts and failures

---

## Support and Troubleshooting

### Common Issues

1. **"Owner must be a valid customer user"**
   - Ensure the user exists and has user_type = 'customer'

2. **"User already in workspace"**
   - Check if the user is already a member of the workspace

3. **"Workspace not found"**
   - Verify the workspace ID exists and is accessible

4. **"User not found"**
   - Ensure the user exists in the system before adding to workspace

### Debug Mode

Enable debug logging by setting the appropriate log level in your environment configuration.

---

## Contributing

When contributing to the workspace management system:

1. Follow the existing code patterns and conventions
2. Add comprehensive tests for new features
3. Update this documentation for any API changes
4. Ensure proper error handling and validation
5. Follow security best practices 