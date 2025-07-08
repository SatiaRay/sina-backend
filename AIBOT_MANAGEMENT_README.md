# AiBot Management API

This document describes the comprehensive AiBot management system implemented for the AI Chatbot application.

## Features

- **AiBot Creation**: Create AiBots with owners and workspace association
- **AiBot Management**: Update, delete, and list AiBots with pagination
- **Document Management**: Add/remove documents to/from AiBots with vectorization support
- **Statistics**: Get comprehensive statistics for each AiBot
- **Workspace Integration**: Full integration with workspace management system
- **Security**: Proper validation and access control
- **Filtering**: Filter AiBots by workspace and owner

## API Endpoints

### Authentication Required
All endpoints require authentication via JWT Bearer token in the Authorization header:
```
Authorization: Bearer <your_jwt_token>pytest-asyncio
```

### Access Control
- Only customer users can be AiBot owners
- AiBot owners must have access to the associated workspace
- Documents must belong to the same workspace as the AiBot

---

## 1. AiBot Creation

### POST `/aibots/`
Create a new AiBot.

**Request Body:**
```json
{
  "name": "My AI Assistant",
  "workspace_id": 1,
  "owner_id": 1
}
```

**Response (200):**
```json
{
  "id": 1,
  "name": "My AI Assistant",
  "workspace_id": 1,
  "owner_id": 1,
  "created_at": "2024-01-01T00:00:00",
  "updated_at": "2024-01-01T00:00:00"
}
```

**Security Rules:**
- Workspace must exist
- Owner must be a valid customer user
- Owner must have access to the workspace
- AiBot name is required

---

## 2. AiBot Listing

### GET `/aibots/`
Get all AiBots with pagination and filtering.

**Query Parameters:**
- `page` (int, default: 1): Page number (starting from 1)
- `per_page` (int, default: 10): Number of AiBots per page (max: 100)
- `workspace_id` (int, optional): Filter by workspace ID
- `owner_id` (int, optional): Filter by owner ID

**Example Request:**
```
GET /aibots/?page=1&per_page=5&workspace_id=1
```

**Response (200):**
```json
{
  "aibots": [
    {
      "id": 1,
      "name": "My AI Assistant",
      "workspace_id": 1,
      "owner_id": 1,
      "created_at": "2024-01-01T00:00:00",
      "updated_at": "2024-01-01T00:00:00"
    },
    {
      "id": 2,
      "name": "Support Bot",
      "workspace_id": 1,
      "owner_id": 2,
      "created_at": "2024-01-01T10:00:00",
      "updated_at": "2024-01-01T10:00:00"
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

## 3. AiBot Detail Retrieval

### GET `/aibots/{aibot_id}`
Get detailed AiBot information.

**Response (200):**
```json
{
  "id": 1,
  "name": "My AI Assistant",
  "workspace_id": 1,
  "owner_id": 1,
  "created_at": "2024-01-01T00:00:00",
  "updated_at": "2024-01-01T00:00:00"
}
```

**Response (404):**
```json
{
  "detail": "AiBot not found"
}
```

---

## 4. AiBot Updates

### PUT `/aibots/{aibot_id}`
Update AiBot information.

**Request Body:**
```json
{
  "name": "Updated AI Assistant Name"
}
```

**Response (200):**
```json
{
  "id": 1,
  "name": "Updated AI Assistant Name",
  "workspace_id": 1,
  "owner_id": 1,
  "created_at": "2024-01-01T00:00:00",
  "updated_at": "2024-01-01T10:00:00"
}
```

**Security Rules:**
- All fields are optional
- Only provided fields will be updated

---

## 5. AiBot Deletion

### DELETE `/aibots/{aibot_id}`
Delete an AiBot.

**Response (204):**
No content returned.

**Security Rules:**
- AiBot and all associated relationships are deleted
- This action cannot be undone

---

## 6. Document Management in AiBots

### POST `/aibots/{aibot_id}/documents`
Add a document to an AiBot.

**Request Body:**
```json
{
  "document_id": 1,
  "vectorize_id": "chroma_doc_123"
}
```

**Response (200):**
```json
{
  "document_id": 1,
  "vectorize_id": "chroma_doc_123",
  "created_at": "2024-01-01T10:00:00"
}
```

**Security Rules:**
- Document must exist and belong to the same workspace as the AiBot
- Document cannot be added if already associated with this AiBot
- `vectorize_id` is optional and stores the Chroma DB document ID

---

## 7. Remove Document from AiBot

### DELETE `/aibots/{aibot_id}/documents/{document_id}`
Remove a document from an AiBot.

**Response (204):**
No content returned.

**Security Rules:**
- Document must be currently associated with the AiBot

---

## 8. List AiBot Documents

### GET `/aibots/{aibot_id}/documents`
Get all documents associated with an AiBot.

**Response (200):**
```json
[
  {
    "document_id": 1,
    "vectorize_id": "chroma_doc_123",
    "created_at": "2024-01-01T10:00:00"
  },
  {
    "document_id": 2,
    "vectorize_id": "chroma_doc_456",
    "created_at": "2024-01-01T11:00:00"
  }
]
```

---

## 9. AiBot Statistics

### GET `/aibots/{aibot_id}/stats`
Get comprehensive statistics for an AiBot.

**Response (200):**
```json
{
  "aibot_id": 1,
  "name": "My AI Assistant",
  "documents_count": 5,
  "chats_count": 12,
  "workflows_count": 3,
  "instructions_count": 8,
  "created_at": "2024-01-01T00:00:00",
  "updated_at": "2024-01-01T10:00:00"
}
```

---

## Usage Examples

### 1. Create an AiBot
```bash
curl -X POST "http://localhost:8000/aibots/" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Customer Support Bot",
    "workspace_id": 1,
    "owner_id": 1
  }'
```

### 2. List All AiBots
```bash
curl -X GET "http://localhost:8000/aibots/?page=1&per_page=5" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### 3. List AiBots by Workspace
```bash
curl -X GET "http://localhost:8000/aibots/?workspace_id=1" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### 4. Get AiBot Details
```bash
curl -X GET "http://localhost:8000/aibots/1" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### 5. Update AiBot
```bash
curl -X PUT "http://localhost:8000/aibots/1" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Updated Support Bot"
  }'
```

### 6. Add Document to AiBot
```bash
curl -X POST "http://localhost:8000/aibots/1/documents" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "document_id": 1,
    "vectorize_id": "chroma_doc_123"
  }'
```

### 7. List AiBot Documents
```bash
curl -X GET "http://localhost:8000/aibots/1/documents" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### 8. Remove Document from AiBot
```bash
curl -X DELETE "http://localhost:8000/aibots/1/documents/1" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### 9. Get AiBot Statistics
```bash
curl -X GET "http://localhost:8000/aibots/1/stats" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### 10. Delete AiBot
```bash
curl -X DELETE "http://localhost:8000/aibots/1" \
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
  "detail": "Document already associated with this AiBot"
}
```

### 403 Forbidden
```json
{
  "detail": "Owner must have access to the workspace."
}
```

### 404 Not Found
```json
{
  "detail": "AiBot not found"
}
```

```json
{
  "detail": "Workspace not found"
}
```

```json
{
  "detail": "Document not found or not accessible"
}
```

```json
{
  "detail": "Document not associated with this AiBot"
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

Run the AiBot management tests:

```bash
# Run all AiBot tests
pytest tests/api/test_aibot.py -v

# Run specific test
pytest tests/api/test_aibot.py::TestAiBotAPI::test_create_aibot_success -v
```

---

## Database Schema

### AiBot Model
```sql
CREATE TABLE aibots (
    id INTEGER PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(255) NOT NULL,
    workspace_id INTEGER NOT NULL,
    owner_id INTEGER NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (workspace_id) REFERENCES workspaces(id),
    FOREIGN KEY (owner_id) REFERENCES users(id),
    INDEX idx_workspace_id (workspace_id),
    INDEX idx_owner_id (owner_id)
);
```

## Security Features

### Access Control
- **Owner Validation**: Only customer users can be AiBot owners
- **Workspace Access**: Owners must have access to the associated workspace
- **Document Isolation**: Documents must belong to the same workspace as the AiBot

### Data Protection
- Proper foreign key constraints ensure data integrity
- Unique constraints prevent duplicate associations
- Cascade deletion handles related records properly

### Validation Rules
- AiBot name is required
- Workspace must exist before AiBot creation
- Owner must be a valid customer user
- Document must exist and be accessible

---

## Integration with Existing System

The AiBot management system integrates seamlessly with the existing application:

1. **Shared Models**: Uses the same User, Workspace, and Document models
2. **Shared Authentication**: Uses the same JWT authentication system
3. **Database Integration**: Works with existing database migrations
4. **API Consistency**: Follows the same patterns as other API endpoints
5. **Vector Store Integration**: Supports Chroma DB vectorization with `vectorize_id`

---

## Business Logic

### AiBot Ownership
- Only customer users can be AiBot owners
- Owners must have access to the associated workspace
- AiBots are workspace-scoped for proper isolation

### Document Management
- Documents must belong to the same workspace as the AiBot
- Each document-AiBot relationship is tracked separately
- Vectorization IDs are stored for Chroma DB integration

### AiBot Lifecycle
1. **Creation**: AiBot is created with an owner and workspace
2. **Configuration**: Documents, workflows, and instructions are added
3. **Operation**: AiBot processes chats and workflows
4. **Deletion**: AiBot and all relationships are removed

---

## Vector Store Integration

The AiBot system includes support for vector store integration:

### Vectorization Support
- `vectorize_id` field stores Chroma DB document identifiers
- Enables seamless integration with vector search capabilities
- Supports document retrieval and similarity search

### Usage Pattern
1. Document is added to AiBot with optional `vectorize_id`
2. Vector store processes and indexes the document
3. AiBot can retrieve relevant documents for chat responses
4. Vector search results are linked back to original documents

---

## Future Enhancements

- [ ] AiBot templates and cloning
- [ ] Advanced document processing pipelines
- [ ] AiBot performance analytics
- [ ] Bulk document operations
- [ ] AiBot sharing and collaboration
- [ ] AiBot backup and restore
- [ ] Advanced vector store integration
- [ ] AiBot-specific settings and configurations
- [ ] AiBot audit trail
- [ ] AiBot notifications and alerts
- [ ] AiBot resource management
- [ ] AiBot branding and customization
- [ ] AiBot integration with external tools
- [ ] AiBot performance monitoring
- [ ] Multi-language support for AiBots
- [ ] AiBot conversation history management
- [ ] AiBot training and fine-tuning capabilities
- [ ] AiBot API rate limiting and quotas
- [ ] AiBot webhook integrations
- [ ] AiBot conversation analytics

---

## API Versioning

The AiBot API follows the same versioning strategy as the rest of the application. All endpoints are prefixed with `/aibots/` and are part of the main API version.

---

## Rate Limiting

AiBot API endpoints are subject to the same rate limiting policies as other API endpoints in the application.

---

## Monitoring and Logging

All AiBot operations are logged for audit purposes:
- AiBot creation, updates, and deletion
- Document additions and removals
- Statistics retrieval
- Access attempts and failures

---

## Support and Troubleshooting

### Common Issues

1. **"Owner must be a valid customer user"**
   - Ensure the user exists and has user_type = 'customer'

2. **"Workspace not found"**
   - Verify the workspace ID exists and is accessible

3. **"Document not found or not accessible"**
   - Ensure the document exists and belongs to the same workspace as the AiBot

4. **"Document already associated with this AiBot"**
   - Check if the document is already linked to the AiBot

5. **"Owner must have access to the workspace"**
   - Ensure the owner has proper access to the workspace

### Debug Mode

Enable debug logging by setting the appropriate log level in your environment configuration.

---

## Contributing

When contributing to the AiBot management system:

1. Follow the existing code patterns and conventions
2. Add comprehensive tests for new features
3. Update this documentation for any API changes
4. Ensure proper error handling and validation
5. Follow security best practices
6. Test vector store integration thoroughly 