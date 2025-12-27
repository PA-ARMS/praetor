# SCOTUS Database - Industry Standards Implementation

## Overview

This system implements industry-standard practices for SCOTUS opinion databases used by legal professionals and legal tech companies.

## Standards Implemented

### 1. Data Sources (Industry Standard)

#### CAP (Caselaw Access Project) - Harvard Law School
- **Status**: ✅ Primary source for historical opinions
- **Coverage**: 1790-present (comprehensive)
- **Why**: Industry-standard source used by legal tech professionals
- **API**: Free API key available at https://case.law/user/register/
- **Format**: Structured JSON with proper citations

#### SCOTUS.gov (Official)
- **Status**: ✅ Primary source for recent opinions
- **Coverage**: 2017-present (slip opinions, bound volumes)
- **Why**: Official government source, authoritative
- **Format**: PDF with official formatting

### 2. Citation Standards

#### Bluebook Format
- **Standard**: Bluebook citation format (industry standard)
- **Format**: `[Volume] U.S. [Page]` (e.g., "606 U.S. 748")
- **Implementation**: 
  - Citation extraction from opinion text
  - Citation normalization to Bluebook format
  - Citation validation

### 3. Metadata Schema (Industry Standard)

Each opinion includes:
- **Citation**: Bluebook-formatted citation
- **Docket Number**: Official docket (e.g., "24-316")
- **Case Name**: Full case name (e.g., "Kennedy v. Braidwood Management, Inc.")
- **Decision Date**: ISO 8601 format
- **Justice/Author**: Opinion author
- **Volume**: U.S. Reports volume number
- **Page**: U.S. Reports page number
- **Source**: Data source (CAP, SCOTUS.gov, etc.)
- **Provenance**: Chain of custody tracking

### 4. Data Quality Standards

#### Validation
- Citation format validation
- Date validation
- Text completeness checks (minimum 200 characters)
- Source verification

#### Provenance Tracking
- Source URL tracking
- API endpoint tracking
- Fetch timestamp
- Data version tracking

### 5. File Formats

#### Text Files (CAP)
- Format: UTF-8 plain text
- Encoding: Standardized for long-term storage
- Structure: Full opinion text with proper formatting

#### PDF Files (SCOTUS.gov)
- Format: PDF/A (archival standard)
- Quality: High-resolution for OCR accuracy
- Metadata: Embedded metadata preserved

### 6. API Integration Standards

#### Rate Limiting
- Respectful API usage
- Exponential backoff on rate limits
- Progress tracking

#### Error Handling
- Graceful degradation
- Retry logic
- Error logging

#### Authentication
- Secure API key storage (environment variables)
- Token-based authentication
- No hardcoded credentials

## Implementation

### Scripts

1. **`scripts/fetch_scotus_industry_standard.py`**
   - Uses CAP API (industry standard)
   - Implements Bluebook citation normalization
   - Proper metadata extraction
   - Data provenance tracking

2. **`scripts/fetch_scotus_opinions.py`**
   - Fetches recent opinions from SCOTUS.gov
   - Official government source
   - PDF format preservation

3. **`scripts/ingest_scotus_opinions.py`**
   - Ingests with proper metadata
   - Citation extraction and validation
   - RAG system integration

## Usage

### Get CAP API Key (Free)

1. Visit: https://case.law/user/register/
2. Register for free account
3. Get API key from: https://case.law/user/profile/
4. Set environment variable: `CAP_API_KEY=your_key_here`

### Run Industry-Standard Fetcher

```bash
# Set API key
export CAP_API_KEY=your_key_here  # Linux/Mac
set CAP_API_KEY=your_key_here     # Windows

# Run fetcher
python scripts/fetch_scotus_industry_standard.py

# Ingest into RAG system
python scripts/ingest_scotus_opinions.py
```

## Expected Results

- **Historical (1790-2016)**: 10,000+ opinions from CAP
- **Recent (2017-2025)**: ~467 opinions from SCOTUS.gov
- **Total**: Comprehensive SCOTUS database with 200+ years of decisions
- **Format**: Industry-standard citations, metadata, and provenance

## Compliance

This implementation follows:
- Bluebook citation standards
- Legal tech industry best practices
- Data provenance requirements
- Citation validation standards
- Metadata schema standards

## References

- CAP (Caselaw Access Project): https://case.law/
- Bluebook Citation Manual: https://www.legalbluebook.com/
- SCOTUS.gov: https://www.supremecourt.gov/







