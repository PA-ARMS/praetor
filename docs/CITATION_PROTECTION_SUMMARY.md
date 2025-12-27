# Citation Protection System - Summary

## Problem
The system was hallucinating Virginia Code citations (e.g., § 18.2-50, § 18.2-56, § 19.2-274, § 19.2-307) for self-defense questions, even though these statutes don't exist or aren't relevant to self-defense.

## Solution - Multi-Layer Protection

### Layer 1: Pre-Generation Whitelist (PRIMARY PROTECTION)
**Location:** `server/routes/chat.py` lines 582-625

**What it does:**
- Extracts ALL Virginia Code citations from retrieved sources
- Creates an explicit whitelist that is sent to the LLM BEFORE generation
- The LLM sees exactly what statutes it can cite
- If no statutes are found, explicitly states "NO VIRGINIA CODE SECTIONS FOUND"

**Format sent to LLM:**
```
================================================================================
CRITICAL: AVAILABLE STATUTES AND CASES IN SOURCES
================================================================================
YOU MAY ONLY CITE THE FOLLOWING STATUTES THAT APPEAR IN THE SOURCES:
  - § 18.2-51.2
  - § 18.2-57.2
  (or "NO VIRGINIA CODE SECTIONS FOUND" if empty)

ABSOLUTE RULE: DO NOT cite any statute or case NOT listed above.
FORBIDDEN: Do NOT cite § 18.2-50, § 18.2-56, § 18.2-57, § 19.2-274, or § 19.2-307 unless they appear in the list above.
================================================================================
```

### Layer 2: Enhanced System Prompt
**Location:** `server/services/guardrails_service.py` lines 242-276

**What it does:**
- Explicitly forbids citing statutes not in context
- Provides specific examples of incorrect citations
- Instructs AI to state "common law defense" when no statute exists

### Layer 3: Post-Generation Validation
**Location:** `server/services/guardrails_service.py` lines 302-391

**What it does:**
- Extracts all citations from the generated response
- Validates them against:
  1. Citations found in retrieved sources
  2. Citations in the entire database
  3. Known incorrect citations list
- Appends warnings if unverified citations are found

**Known Incorrect Citations:**
- § 18.2-50 (doesn't exist for self-defense)
- § 18.2-56 (incorrect)
- § 18.2-57 (incorrect)
- § 19.2-274 (incorrect)
- § 19.2-307 (about juvenile records, not self-defense)

### Layer 4: Case Name Validation
**Location:** `server/services/guardrails_service.py` lines 310-325

**What it does:**
- Detects generic case names without proper citations (e.g., "Commonwealth v. Smith")
- Validates that cases appear in sources with proper citations
- Warns if generic case names are cited without full citations

## How It Works Together

1. **Before Generation:** LLM sees whitelist of available statutes
2. **During Generation:** System prompt explicitly forbids hallucination
3. **After Generation:** Validation checks all citations and flags issues
4. **User Sees:** Response with warnings if any unverified citations detected

## Expected Behavior

### For Self-Defense Questions:
- If sources contain no statutes: Response states "Self-defense in Virginia is primarily a common law defense. No specific Virginia Code section was found in the available sources."
- If sources contain statutes: Only those statutes are cited
- If AI tries to cite forbidden statutes: Warning is appended to response

## Testing

To verify the system works:
1. Ask a self-defense question
2. Check that response does NOT cite § 18.2-50, § 18.2-56, § 18.2-57, § 19.2-274, or § 19.2-307
3. Check that response either:
   - Cites only statutes from the whitelist, OR
   - States that self-defense is common law with no statute found

## Status

✅ **IMPLEMENTED AND ACTIVE**
- Pre-generation whitelist: ✅ Active
- Enhanced system prompt: ✅ Active  
- Post-generation validation: ✅ Active
- Case name validation: ✅ Active
- Known incorrect list: ✅ Active







