# Operator Management API

This document describes the operator management system implemented for the AI Chatbot application.

## Features

- **Operator Creation**: Create operator users
- **Operator Management**: Update, delete, and list operators
- **Pagination**: Get all operators with pagination
- **Security**: Only operator users can access these endpoints

---

## API Endpoints

### Authentication Required
All endpoints require authentication via JWT Bearer token in the Authorization header:
```
Authorization: Bearer <your_jwt_token>
```

### Access Control
- Only users with `user_type == 'operator'` can access these endpoints

---

## 1. Operator Creation

### POST `/operators/`
Create a new operator user.

**Request Body:**
```json
{
  "email": "operator@example.com",
  "password": "password123",
  "first_name": "Op",
  "last_name": "Erator"
}
```

**Response (200):**
```json
{
  "id": 1,
  "email": "operator@example.com",
  "first_name": "Op",
  "last_name": "Erator",
  "is_active": true,
  "created_at": "2024-01-01T00:00:00",
  "updated_at": "2024-01-01T00:00:00"
}
```

---

## 2. Operator Listing

### GET `/operators/`
Get all operators with pagination.

**Query Parameters:**
- `page` (int, default: 1): Page number (starting from 1)
- `per_page` (int, default: 10): Number of operators per page (max: 100)

**Example Request:**
```
GET /operators/?page=1&per_page=5
```

**Response (200):**
```json
{
  "operators": [
    {
      "id": 1,
      "email": "operator@example.com",
      "first_name": "Op",
      "last_name": "Erator",
      "is_active": true,
      "created_at": "2024-01-01T00:00:00",
      "updated_at": "2024-01-01T00:00:00"
    }
  ],
  "total": 1,
  "page": 1,
  "per_page": 5,
  "total_pages": 1,
  "has_next": false,
  "has_prev": false
}
```

---

## 3. Operator Detail Retrieval

### GET `/operators/{operator_id}`
Get detailed operator information.

**Response (200):**
```json
{
  "id": 1,
  "email": "operator@example.com",
  "first_name": "Op",
  "last_name": "Erator",
  "is_active": true,
  "created_at": "2024-01-01T00:00:00",
  "updated_at": "2024-01-01T00:00:00"
}
```

**Response (404):**
```json
{
  "detail": "Operator not found"
}
```

---

## 4. Operator Updates

### PUT `/operators/{operator_id}`
Update operator information.

**Request Body:**
```json
{
  "first_name": "Updated Name",
  "is_active": false
}
```

**Response (200):**
```json
{
  "id": 1,
  "email": "operator@example.com",
  "first_name": "Updated Name",
  "last_name": "Erator",
  "is_active": false,
  "created_at": "2024-01-01T00:00:00",
  "updated_at": "2024-01-01T10:00:00"
}
```

---

## 5. Operator Deletion

### DELETE `/operators/{operator_id}`
Delete an operator user.

**Response (204):**
No content returned.

---

## Usage Examples

### 1. Create an Operator
```bash
curl -X POST "http://localhost:8000/operators/" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "operator@example.com",
    "password": "password123",
    "first_name": "Op",
    "last_name": "Erator"
  }'
```

### 2. List All Operators
```bash
curl -X GET "http://localhost:8000/operators/?page=1&per_page=5" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### 3. Get Operator Details
```bash
curl -X GET "http://localhost:8000/operators/1" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### 4. Update Operator
```bash
curl -X PUT "http://localhost:8000/operators/1" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "first_name": "Updated Name",
    "is_active": false
  }'
```

### 5. Delete Operator
```bash
curl -X DELETE "http://localhost:8000/operators/1" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

---

## Error Responses

### 400 Bad Request
```json
{
  "detail": "Email already registered"
}
```

### 403 Forbidden
```json
{
  "detail": "Operator access required for this operation"
}
```

### 404 Not Found
```json
{
  "detail": "Operator not found"
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

Run the operator management tests:

```bash
# Run all operator tests
pytest tests/api/test_operator.py -v
``` 