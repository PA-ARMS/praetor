# Document Upload and Understanding Guide

## Overview

The system can now read, understand, and learn from uploaded legal documents. When you upload a document:

1. **Document Understanding**: AI analyzes the document to extract key information
2. **RAG Indexing**: Document is added to the searchable corpus
3. **Scenario Processing**: If it's a legal case, it's automatically added to the learning system

## Supported File Types

The system can read and understand:

- **PDF** (`.pdf`) - Legal briefs, motions, opinions, contracts
- **Word Documents** (`.docx`) - Legal documents, memos
- **PowerPoint** (`.pptx`) - Presentations, case summaries
- **Text Files** (`.txt`, `.md`) - Plain text documents
- **HTML** (`.html`, `.htm`) - Web pages, online documents
- **Excel/CSV** (`.xlsx`, `.xls`, `.csv`) - Spreadsheets, data tables

## What the System Understands

When you upload a document, the AI automatically extracts:

### Document Analysis
- **Document Type**: Motion, Brief, Contract, Case Law, etc.
- **Summary**: 2-3 sentence summary of the document
- **Key Points**: Main points and findings
- **Legal Concepts**: Legal topics mentioned (Contract, Tort, Criminal, etc.)

### Entity Extraction
- **Parties**: Plaintiff, Defendant, Petitioner, Respondent
- **Case Numbers**: Docket numbers, case IDs
- **Dates**: Important dates mentioned
- **Statutes**: Virginia Code sections, USC citations
- **Courts**: Court names and jurisdictions

### Learning Integration
If the document is identified as a legal case:
- **Facts Extraction**: Key facts without the outcome
- **Outcome Detection**: Case outcome (Plaintiff Win, Defendant Win, etc.)
- **Scenario Creation**: Added to the learning database
- **Metadata**: Case type, jurisdiction, key factors

## How to Upload Documents

### Via Web Interface

1. Navigate to the document upload section
2. Select one or more files
3. Choose jurisdiction (Virginia or Federal)
4. Click "Upload"
5. Review the analysis results

### Via API

```bash
curl -X POST "http://localhost:5000/api/rag/upload-document" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@document.pdf" \
  -F "jurisdiction=Virginia"
```

## Understanding the Results

After upload, you'll receive:

```json
{
  "status": "success",
  "message": "Document successfully indexed and analyzed",
  "indexed": true,
  "text_length": 5234,
  "understanding": {
    "summary": "Motion for summary judgment in contract dispute...",
    "document_type": "Motion",
    "key_points": [
      "Motion seeks summary judgment",
      "Contract breach alleged",
      "Statute of limitations at issue"
    ],
    "legal_concepts": ["Contract", "Civil Procedure"],
    "entities": {
      "parties": ["Smith v. Jones"],
      "case_numbers": ["Case No. 2024-12345"],
      "statutes": ["Va. Code § 8.01-243"],
      "dates": ["2024-01-15"]
    }
  },
  "scenario_processed": true,
  "scenario_id": "upload_document_1234567890",
  "scenario_outcome": "Defendant Win"
}
```

## Learning System Integration

### Automatic Processing

When a document is identified as a legal case:
- ✅ Facts are extracted (without outcome)
- ✅ Outcome is detected
- ✅ Document is added to scenario database
- ✅ Available for case outcome prediction
- ✅ Used in continuous learning loop

### What Makes a Document Processable?

A document is processed as a scenario if it contains:
- Legal case indicators (plaintiff, defendant, case number, etc.)
- Identifiable outcome (granted, denied, judgment, etc.)
- Sufficient facts (100+ characters)
- Legal concepts or entities

### Manual Review

Documents that can't be automatically processed:
- May not have clear outcome
- May not be a legal case
- May have insufficient facts

These are still indexed for search but not added to learning system.

## Best Practices

### For Better Understanding

1. **Upload Complete Documents**
   - Include full text, not excerpts
   - Ensure documents are readable (not scanned images without OCR)

2. **Use Descriptive Filenames**
   - Include case name or document type
   - Example: "Smith_v_Jones_Motion_Summary_Judgment.pdf"

3. **Upload Related Documents Together**
   - Motions with supporting briefs
   - Cases with opinions
   - Contracts with amendments

### For Learning System

1. **Upload Cases with Clear Outcomes**
   - Court opinions with rulings
   - Motions with decisions
   - Cases with final judgments

2. **Include Metadata in Filenames**
   - Case name
   - Document type
   - Date (if relevant)

3. **Upload Diverse Cases**
   - Different case types
   - Different outcomes
   - Different jurisdictions

## Use Cases

### 1. Upload Firm's Case Library

Upload your firm's past cases to:
- Build internal knowledge base
- Improve outcome predictions
- Learn from firm's case history

### 2. Upload Opposing Party Documents

Upload opposing party's briefs/motions to:
- Analyze their arguments
- Find similar cases
- Predict likely outcomes

### 3. Upload Research Materials

Upload research documents to:
- Expand searchable corpus
- Improve RAG responses
- Build comprehensive knowledge base

## Troubleshooting

### Document Not Processed as Scenario

**Possible Reasons:**
- Document doesn't appear to be a legal case
- Outcome cannot be determined
- Insufficient facts extracted

**Solution:**
- Document is still searchable via RAG
- Review document to ensure it's a complete case
- Check that outcome is clearly stated

### Understanding Incomplete

**Possible Reasons:**
- Document is very long (only first 10,000 chars analyzed)
- Document format not fully supported
- AI analysis failed

**Solution:**
- Full text is still indexed for search
- Understanding provides summary, not full analysis
- Use search to find specific information

### Upload Fails

**Possible Reasons:**
- File too large
- Unsupported format
- Server error

**Solution:**
- Check file size (recommended: < 50 MB)
- Verify file format is supported
- Check server logs for details

## API Reference

### Upload Document

**Endpoint:** `POST /api/rag/upload-document`

**Parameters:**
- `file` (required): File to upload
- `jurisdiction` (optional): "Virginia" or "Federal" (default: "Virginia")
- `analyze_against_scenarios` (optional): "true" or "false" (default: "false")

**Response:**
- `status`: "success" or error
- `understanding`: Document analysis
- `scenario_processed`: Whether added to learning system
- `scenario_id`: ID if processed as scenario

## Integration with Other Features

### RAG Search

Uploaded documents are immediately searchable:
- Use chat interface to ask questions
- System will find relevant information from uploaded docs
- Citations include document source

### Learning System

Processed scenarios are used for:
- Case outcome prediction
- Continuous learning loop
- Pattern detection
- Error analysis

### Form Generation

Uploaded documents can inform:
- Form templates
- Procedural requirements
- Court-specific formatting

## Security and Privacy

### Data Storage
- Documents stored locally on server
- Not shared with external services
- Access controlled by user roles

### Confidentiality
- All documents are logged
- Access tracked in audit logs
- Follow firm's confidentiality policies

### Best Practices
- Avoid uploading documents with sensitive PII
- Use generic case descriptions when possible
- Review uploaded documents regularly

## Examples

### Example 1: Upload Court Opinion

**File:** `Smith_v_Jones_Opinion_2024.pdf`

**Result:**
- Document type: "Case Law"
- Outcome: "Plaintiff Win"
- Added to scenario database
- Searchable via RAG

### Example 2: Upload Motion

**File:** `Motion_Summary_Judgment_Breach_Contract.docx`

**Result:**
- Document type: "Motion"
- Outcome: "Defendant Win" (motion granted)
- Added to scenario database
- Key points extracted
- Statutes cited identified

### Example 3: Upload Contract

**File:** `Service_Agreement_2024.pdf`

**Result:**
- Document type: "Contract"
- Not processed as scenario (no outcome)
- Indexed for search
- Key terms extracted
- Available for contract analysis queries

---

**Last Updated**: [Date]
**Version**: 1.0

