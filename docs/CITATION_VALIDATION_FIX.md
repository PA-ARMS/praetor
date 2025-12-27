# Citation Validation Fix - Self-Defense Statutes

## Problem Identified

The system was citing incorrect Virginia Code sections for self-defense:
- **§ 19.2-274** - Incorrectly cited for self-defense with non-deadly force
- **§ 18.2-56** - Incorrectly cited for justifiable homicide  
- **§ 18.2-57** - Incorrectly cited for justifiable homicide in defense

## Root Cause

The AI was hallucinating statute citations from its training data that were not present in the provided RAG context. This violates Article I of the AI Laws: "Fidelity to Truth."

## Correct Legal Framework

In Virginia, **self-defense is primarily a common law defense**, not a statutory defense. There is no specific Virginia Code section that defines self-defense.

### Relevant Virginia Code Sections:
- **§ 18.2-51.2** - Aggravated malicious wounding (the charge itself)
- Self-defense is a common law affirmative defense that can be raised against this charge

### Key Self-Defense Elements (Common Law):
1. **Reasonable apprehension of imminent danger** - The defendant must reasonably believe they face immediate harm
2. **Necessity** - The use of force must be necessary to prevent the harm
3. **Proportionality** - The force used must be proportional to the threat
4. **No duty to retreat** - Virginia follows the "stand your ground" principle (no duty to retreat before using deadly force)

## Fixes Implemented

### 1. Enhanced Citation Validation (`server/services/guardrails_service.py`)
- Improved regex patterns to catch more citation variations
- Added database verification for all cited statutes
- Now checks both metadata and document text for citation existence
- Warns when citations are not found in the verified database

### 2. Strengthened System Prompt
- Added explicit instruction: "You MUST NOT cite Virginia Code sections (e.g., § 18.2-56, § 19.2-274) unless they EXACTLY appear in the provided context."
- Added example of error to avoid
- Added instruction to state when self-defense is common law and no specific statute exists

### 3. Post-Processing Validation
- All citations in responses are now validated against the database
- Warnings are automatically appended when unverified citations are detected

## Testing

To verify the fix works:
1. Ask a self-defense question
2. Check that the response does NOT cite § 18.2-56, § 18.2-57, or § 19.2-274
3. Check that the response correctly states self-defense is a common law defense
4. Verify that any cited statutes actually exist in the database

## Industry Standard

This fix ensures compliance with:
- **Article I: Fidelity to Truth** - No fabrication of statutes
- **Article IV: Precision** - Only cite what exists in sources
- **Bluebook Citation Standards** - Only cite verifiable authorities






