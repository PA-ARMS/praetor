# SCOTUS Database Building Guide

## Overview

This guide explains how to build a comprehensive SCOTUS opinion database covering 200+ years of Supreme Court decisions.

## Current Status

### Recent Opinions (2017-2025)
- **Source**: SCOTUS.gov official website
- **Coverage**: Terms 17-25 (October 2017 - October 2025)
- **Count**: ~374 slip opinions + 83 bound volumes + 10 preliminary prints
- **Status**: ✅ Fetching script created and running

### Historical Opinions (1700s-2016)
- **Sources Available**:
  1. **CourtListener** - Most comprehensive, but requires API key or bulk download
  2. **GovInfo Bulk Data** - Official government source (1937-1975)
  3. **Library of Congress** - Digitized United States Reports
  4. **CAP (Caselaw Access Project)** - Harvard's historical database (requires free API key)

## How to Build Complete Database

### Option 1: CourtListener Bulk Download (Recommended)

1. **Get CourtListener Account** (Free):
   - Visit: https://www.courtlistener.com/
   - Create free account
   - Request API key (optional but recommended)

2. **Download Bulk Data**:
   - Visit: https://www.courtlistener.com/api/bulk-data/
   - Download SCOTUS opinions bulk ZIP
   - Extract and process with ingestion script

### Option 2: CAP (Caselaw Access Project)

1. **Get Free API Key**:
   - Visit: https://case.law/
   - Register for free API key
   - Set environment variable: `CAP_API_KEY=your_key`

2. **Use CAP API**:
   - CAP has comprehensive historical SCOTUS coverage
   - Free tier allows reasonable API usage
   - Well-structured data with citations

### Option 3: GovInfo Bulk Data

1. **Download Official Bulk Data**:
   - Visit: https://www.govinfo.gov/bulkdata
   - Download SCOTUS decisions (1937-1975)
   - Process XML/ZIP files

### Option 4: Library of Congress

1. **Access Digitized Reports**:
   - Visit: https://www.loc.gov/collections/united-states-reports/
   - Download digitized volumes
   - Process PDFs

## Scripts Available

1. **`scripts/fetch_scotus_opinions.py`**
   - Fetches recent opinions from SCOTUS.gov
   - Downloads slip opinions, bound volumes, preliminary prints
   - Status: ✅ Working

2. **`scripts/fetch_scotus_historical.py`**
   - Fetches historical opinions from CourtListener API
   - Requires API key for full access
   - Status: ⚠️ Needs API key or bulk download

3. **`scripts/ingest_scotus_opinions.py`**
   - Ingests all SCOTUS opinions into RAG system
   - Extracts metadata (citations, dockets, case names)
   - Status: ✅ Ready

4. **`scripts/fetch_all_scotus.py`**
   - Master script that runs everything
   - Combines recent + historical
   - Status: ✅ Ready

## Quick Start

### For Recent Opinions Only (2017-2025):
```bash
python scripts/fetch_scotus_opinions.py
python scripts/ingest_scotus_opinions.py
```

### For Complete Database (Requires API Keys):
1. Get CourtListener or CAP API key
2. Set environment variable: `COURTLISTENER_API_KEY=your_key` or `CAP_API_KEY=your_key`
3. Run: `python scripts/fetch_all_scotus.py`

## Expected Results

- **Recent (2017-2025)**: ~467 files (374 opinions + 83 volumes + 10 prints)
- **Historical (1700s-2016)**: 10,000+ opinions from CourtListener/CAP
- **Total**: Comprehensive SCOTUS database with 200+ years of decisions

## Notes

- CourtListener API requires authentication for programmatic access
- Bulk downloads are available without API key but require manual processing
- CAP (Caselaw Access Project) offers free API key with reasonable limits
- GovInfo provides official government data but limited date range (1937-1975)

## Next Steps

1. ✅ Complete recent opinions fetch (currently running)
2. ⏳ Get CourtListener or CAP API key for historical data
3. ⏳ Run historical fetcher
4. ⏳ Ingest all opinions into RAG system
5. ⏳ Verify comprehensive coverage







