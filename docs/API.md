# Virginia Legal AI API Documentation

## Base URL
- Local: `http://localhost:5000`
- Network: `http://[SERVER_IP]:5000`

## Endpoints

### Chat

#### POST `/api/chat/query`
Legal research query with RAG.

**Request:**
```json
{
  "message": "What is the statute of limitations for breach of contract in Virginia?",
  "conversation_id": "optional-id",
  "use_rag": true,
  "max_results": 5
}
```

**Response:**
```json
{
  "response": "Legal analysis with citations...",
  "sources": [
    {
      "source": "Code of Virginia",
      "jurisdiction": "Virginia",
      "excerpt": "Statute text..."
    }
  ],
  "conversation_id": "conversation-id",
  "timestamp": "2025-11-15T13:00:00",
  "warnings": []
}
```

#### POST `/api/chat/stream`
Streaming chat response (Server-Sent Events).

### Forms

#### POST `/api/forms/generate`
Generate legal form from case data.

**Request:**
```json
{
  "form_type": "Motion to Dismiss",
  "court": "Circuit Court of Fairfax County",
  "case_data": {
    "plaintiff": "John Doe",
    "defendant": "Jane Smith",
    "case_number": "CL-2025-12345"
  },
  "generate_workflow": true
}
```

**Response:**
```json
{
  "form_type": "Motion to Dismiss",
  "court": "Circuit Court of Fairfax County",
  "content": "Generated form content...",
  "workflow_info": "Court procedures...",
  "generated_at": "2025-11-15T13:00:00",
  "verification_required": true
}
```

#### POST `/api/forms/workflow`
Get workflow information for a form type.

**Query Parameters:**
- `form_type`: Type of form
- `court`: Court name

### RAG

#### POST `/api/rag/add-document`
Add document to corpus.

#### POST `/api/rag/upload-document`
Upload and index document file.

#### GET `/api/rag/search`
Search corpus.

**Query Parameters:**
- `query`: Search query
- `n_results`: Number of results (default: 5)

#### GET `/api/rag/stats`
Get corpus statistics.

### Documents

#### POST `/api/documents/upload`
Upload document file.

#### GET `/api/documents/list`
List all documents.

## Health Check

#### GET `/health`
Returns server health status.

