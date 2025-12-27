# Anti-Hallucination System - Zero Tolerance for Fabrication

## Overview

This document describes the comprehensive system of guardrails, validations, and restrictions designed to prevent the AI from hallucinating, fabricating, or misrepresenting legal information. **Zero tolerance for errors** - attorneys' clients' freedom depends on accurate legal information.

## Core Principles

1. **Only Use Verified Sources**: The AI must ONLY cite statutes, cases, and legal authorities that appear in the provided database context
2. **No Training Data Usage**: The AI must NOT use information from its training data that is not verified in the database
3. **Explicit Uncertainty**: When information is not found, the system must state uncertainty rather than guessing
4. **Database Verification**: All citations are verified against the entire database, not just search results

## Multi-Layer Protection System

### Layer 1: System Prompt Restrictions

**Location**: `server/services/guardrails_service.py` - `build_system_prompt()`

The system prompt includes explicit restrictions:

```
CRITICAL: SOURCE RESTRICTION - ZERO TOLERANCE FOR HALLUCINATION:
- You MUST ONLY cite statutes, cases, and legal authorities that appear in the provided context
- You MUST NOT cite any legal authority from your training data that is NOT in the provided context
- You MUST NOT invent, fabricate, or guess at statute numbers, case names, or legal citations
- If a statute is mentioned in your training data but NOT in the provided context, you MUST NOT cite it
- If you cannot find information in the provided context, you MUST state: 'No controlling authority found'
- When in doubt, indicate uncertainty rather than providing potentially incorrect information
- Your response must be 100% based on the provided context - nothing else
```

### Layer 2: Context Restrictions

**Location**: `server/routes/chat.py` - Context building

When context is provided to the AI, it includes explicit restrictions:

```
[CRITICAL RESTRICTION: You MUST ONLY cite statutes, cases, and legal authorities that appear 
in the context provided above. Do NOT cite anything from your training data that is not in 
this context. If information is not in the provided context, state 'No controlling authority 
found' or 'This information was not found in the available sources.']
```

### Layer 3: Citation Verification (Database-Wide)

**Location**: `server/services/guardrails_service.py` - `validate_and_correct()`

**Two-Stage Verification Process**:

1. **Stage 1 - Check Retrieved Sources**: Citations are first checked against the sources returned by RAG search
2. **Stage 2 - Database Verification**: If a citation isn't in retrieved sources, it's verified against the **entire database** using exact metadata matching

This prevents false warnings for citations that:
- Exist in the database
- But weren't in the top 50/200 search results
- Are still valid and should not trigger warnings

**Result**: Only citations that **don't exist anywhere in the database** trigger warnings.

### Layer 4: No Sources Enforcement

**Location**: `server/routes/chat.py` - Response generation

When RAG returns no sources:
- The system **forces** the response: "No controlling authority found."
- The AI is **not allowed** to generate a response using training data
- A warning is added: "No legal sources were found in the database for this query"

### Layer 5: AI Laws Enforcement

**Location**: `config/ai_laws.json`

Article I: Fidelity to Truth explicitly prohibits:
- Inventing, fabricating, or misrepresenting statutes, regulations, case law
- Using information not from verifiable primary sources
- Speculating when insufficient facts are provided

### Layer 6: Source Priority Recognition

**Location**: `server/services/rag_service.py` - `_get_source_priority()`

Robust source matching ensures authoritative sources (like "Code of Virginia") are correctly identified even with:
- Case variations
- Additional text appended
- Slight name differences

This ensures proper verification status and warnings.

## How It Works

### Example Flow

1. **User Query**: "What is § 46.2-391?"

2. **RAG Search**: 
   - Searches database for relevant documents
   - Returns top 50 most relevant results
   - Attempts exact citation match first

3. **Context Building**:
   - Includes retrieved sources
   - Adds explicit restriction: "ONLY use provided context"
   - Warns if sources are limited

4. **AI Generation**:
   - AI generates response using ONLY provided context
   - System prompt reinforces: "Do NOT use training data"

5. **Citation Verification**:
   - Extracts all citations from AI response
   - Checks against retrieved sources
   - If not found, checks entire database
   - Only warns about citations that don't exist in database

6. **Response Validation**:
   - Checks for "No controlling authority found" when appropriate
   - Validates citations are from provided sources
   - Adds warnings for unverified citations

## Key Features

### 1. Database-Wide Citation Verification

**Before**: Only checked citations against top 50 search results
- False warnings for citations that exist but weren't in top results

**After**: Checks entire database for citations
- Only warns about citations that truly don't exist
- Verifies citations exist even if not in search results

### 2. Explicit Source Restrictions

**Before**: System prompt said to cite sources, but didn't explicitly forbid training data

**After**: Multiple explicit restrictions:
- In system prompt
- In context instructions
- In verification warnings

### 3. No Sources = No Response

**Before**: AI could generate response using training data when no sources found

**After**: System forces "No controlling authority found" when no sources available

### 4. Uncertainty Indication

**Before**: AI might guess or use training data when uncertain

**After**: System explicitly requires stating uncertainty:
- "No controlling authority found"
- "This information was not found in the available sources"
- "Verify independently"

## Testing & Validation

### How to Verify It's Working

1. **Query with citation not in database**: Should get warning
2. **Query with citation in database but not in top results**: Should NOT get false warning
3. **Query with no sources found**: Should get "No controlling authority found"
4. **Query with limited sources**: Should get warnings about limited sources

### Monitoring

- Review warnings in responses
- Check citation verification logs
- Monitor for false positives/negatives
- Senior partner reviews catch any issues

## Future Enhancements

Potential improvements:
- Real-time database citation lookup during generation (not just post-validation)
- Confidence scoring for each citation
- Automatic source expansion when citations are mentioned but not in context
- Enhanced pattern matching for case citations (not just statutes)

## Critical Reminders

1. **This is a mission-critical system** - Zero tolerance for errors
2. **All legal data must be verified** - No exceptions
3. **When in doubt, indicate uncertainty** - Never guess
4. **Database is the source of truth** - Training data is not
5. **Senior partner reviews** - Catch any remaining issues

## Related Systems

- **Citation Extraction**: Ensures citations are stored in metadata for exact matching
- **Source Priority Recognition**: Ensures authoritative sources are correctly identified
- **Review System**: Allows senior partners to catch and correct any issues
- **User Corrections**: Learning system that incorporates verified corrections










